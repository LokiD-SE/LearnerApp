"""Token cost accounting, an exact-match response cache, and budget guards against unbounded consumption.

Running example: SandPay's merchant-support assistant. Finance wants the cost of every request; the
on-call engineer wants a runaway loop or an abusive client to hit a limit before it hits the invoice.

- ``Price`` / ``request_cost`` - money as ``Decimal``. Prices are per million tokens. The cache multipliers
  default to the ones Anthropic documents for prompt caching (5-minute writes 1.25x the base input price,
  reads 0.1x); other providers price caching differently - pass your provider's numbers.
- ``ResponseCache`` - an application-side cache of whole replies, keyed by a hash of the canonical request.
  Only deterministic requests (temperature 0) that finished normally are stored. Entries expire after
  ``ttl`` seconds; the least recently used entry is evicted when the cache is full.
- ``BudgetGuard`` - per-request token caps, a per-user token bucket of requests, and a daily spend limit:
  mitigations OWASP LLM10:2025 (Unbounded Consumption) lists as input validation, rate limiting and
  resource allocation management.
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

MILLION = Decimal(1_000_000)


@dataclass(frozen=True)
class Price:
    input_per_mtok: Decimal
    output_per_mtok: Decimal
    cache_write_multiplier: Decimal = Decimal("1.25")
    cache_read_multiplier: Decimal = Decimal("0.1")


def request_cost(price: Price, *, input_tokens: int, output_tokens: int, cache_write_tokens: int = 0, cache_read_tokens: int = 0) -> Decimal:
    """Cost in dollars of one request.

    ``input_tokens`` are the uncached input tokens only; cache writes and cache reads are billed at the
    base input price times their multiplier. Negative counts are a bug in the caller: raise ValueError.
    """
    counts = (input_tokens, output_tokens, cache_write_tokens, cache_read_tokens)
    if any(c < 0 for c in counts):
        raise ValueError("token counts must be >= 0")
    base_in = price.input_per_mtok / MILLION
    return (
        input_tokens * base_in
        + cache_write_tokens * base_in * price.cache_write_multiplier
        + cache_read_tokens * base_in * price.cache_read_multiplier
        + output_tokens * price.output_per_mtok / MILLION
    )


def request_key(request: dict[str, Any]) -> str:
    """SHA-256 of the request as canonical JSON (sorted keys, no spaces), so equal requests get equal keys."""
    canonical = json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ResponseCache:
    """Exact-match cache of model replies with a TTL and least-recently-used eviction."""

    def __init__(self, *, max_entries: int, ttl: float, clock: Callable[[], float]):
        if max_entries < 1 or ttl <= 0:
            raise ValueError("max_entries must be >= 1 and ttl > 0")
        self.max_entries = max_entries
        self.ttl = ttl
        self.clock = clock
        self._entries: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def cacheable(request: dict[str, Any]) -> bool:
        """Only requests with temperature 0 are worth caching; sampled replies are meant to vary."""
        return request.get("temperature", 1.0) == 0

    def get_or_call(self, request: dict[str, Any], call: Callable[[dict[str, Any]], Any]) -> tuple[Any, bool]:
        """Return ``(reply, from_cache)``.

        Non-cacheable requests always call (and count neither a hit nor a miss). A cached entry older than
        ``ttl`` is a miss and is removed. A reply is stored only if its ``stop_reason`` is ``"end_turn"`` -
        a cut-off (``max_tokens``) or tool-use reply must not be replayed to the next user.
        """
        if not self.cacheable(request):
            return call(request), False
        key = request_key(request)
        now = self.clock()
        entry = self._entries.get(key)
        if entry is not None:
            stored_at, reply = entry
            if now - stored_at < self.ttl:
                self._entries.move_to_end(key)
                self.hits += 1
                return reply, True
            del self._entries[key]
        self.misses += 1
        reply = call(request)
        if getattr(reply, "stop_reason", None) == "end_turn":
            self._entries[key] = (now, reply)
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
        return reply, False

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


class BudgetExceeded(Exception):
    """A request was refused before it reached the model; ``reason`` names the limit."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class BudgetGuard:
    """Limits checked *before* each model call; ``record`` adds the real cost afterwards.

    - ``max_input_tokens`` / ``max_output_tokens`` per request (reason ``"input_too_large"`` /
      ``"max_tokens_too_high"``);
    - a token bucket per user: ``burst`` requests at most, refilled at ``refill_per_second``
      (reason ``"rate_limited"``);
    - ``daily_budget`` dollars across all users, reset when ``clock() // 86400`` changes
      (reason ``"daily_budget"``) - refused when spent + ``estimated_cost`` would exceed it.
    The checks run in that order, and a refused request does not use a token from the bucket.
    """

    def __init__(
        self,
        *,
        max_input_tokens: int,
        max_output_tokens: int,
        burst: int,
        refill_per_second: float,
        daily_budget: Decimal,
        clock: Callable[[], float],
    ):
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.burst = burst
        self.refill_per_second = refill_per_second
        self.daily_budget = daily_budget
        self.clock = clock
        self._buckets: dict[str, tuple[float, float]] = {}  # user -> (tokens, last refill time)
        self._day = int(clock() // 86400)
        self.spent = Decimal(0)

    def _roll_day(self) -> None:
        day = int(self.clock() // 86400)
        if day != self._day:
            self._day = day
            self.spent = Decimal(0)

    def check(self, user: str, *, input_tokens: int, max_tokens: int, estimated_cost: Decimal) -> None:
        if input_tokens > self.max_input_tokens:
            raise BudgetExceeded("input_too_large")
        if max_tokens > self.max_output_tokens:
            raise BudgetExceeded("max_tokens_too_high")
        now = self.clock()
        tokens, last = self._buckets.get(user, (float(self.burst), now))
        tokens = min(float(self.burst), tokens + (now - last) * self.refill_per_second)
        if tokens < 1:
            self._buckets[user] = (tokens, now)
            raise BudgetExceeded("rate_limited")
        self._roll_day()
        if self.spent + estimated_cost > self.daily_budget:
            self._buckets[user] = (tokens, now)
            raise BudgetExceeded("daily_budget")
        self._buckets[user] = (tokens - 1, now)

    def record(self, cost: Decimal) -> None:
        self._roll_day()
        self.spent += cost
