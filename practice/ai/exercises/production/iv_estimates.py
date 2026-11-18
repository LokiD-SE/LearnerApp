"""Back-of-the-envelope numbers for an LLM feature, the way you size one in a system design interview.

Running example: SandPay's merchant-support assistant. Every price in the tests and the lesson is an
assumption made up for practice - look up your provider's current price list before using real numbers.

- ``daily_cost`` - tokens times price per million tokens, with the cached part of the prompt priced separately.
- ``response_seconds`` - time to first token plus output tokens divided by the output speed.
- ``concurrency`` - Little's law (L = lambda x W): requests in flight = arrival rate x time per request.
- ``max_requests_within_budget`` - how many requests a day a budget pays for.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

SECONDS_PER_DAY = 86_400


@dataclass(frozen=True)
class Workload:
    requests_per_day: int
    input_tokens: int  # per request: system prompt + history + retrieved context + question
    output_tokens: int  # per request
    cached_input_tokens: int = 0  # the part of input_tokens read from a prompt cache


@dataclass(frozen=True)
class Prices:
    """Price per million tokens (assumed numbers, in EUR)."""

    input: float
    output: float
    cached_input: float


def _check(w: Workload) -> None:
    if min(w.requests_per_day, w.input_tokens, w.output_tokens, w.cached_input_tokens) < 0:
        raise ValueError("token counts and requests must not be negative")
    if w.cached_input_tokens > w.input_tokens:
        raise ValueError("cached_input_tokens cannot exceed input_tokens")


def cost_per_request(w: Workload, p: Prices) -> float:
    """Cost of one request in EUR, not rounded."""
    # TODO: (uncached input x input price + cached input x cached price + output x output price) / 1 000 000.
    # Call _check(w) first.
    raise NotImplementedError("cost_per_request")


def daily_cost(w: Workload, p: Prices) -> float:
    """Cost per day in EUR, rounded to cents."""
    # TODO: cost_per_request x requests_per_day, rounded to cents.
    raise NotImplementedError("daily_cost")


def response_seconds(ttft_seconds: float, output_tokens: int, tokens_per_second: float) -> float:
    """Time until the whole reply has streamed: first token, then the rest at the output speed."""
    # TODO: time to first token + output tokens / tokens per second. ValueError for negative
    # inputs or a speed <= 0.
    raise NotImplementedError("response_seconds")


def concurrency(requests_per_day: int, peak_factor: float, seconds_per_request: float) -> int:
    """Requests in flight at the peak (Little's law), rounded up to whole requests."""
    # TODO: Little's law - arrivals per second at the peak (requests/day / 86 400 x peak_factor) x seconds
    # per request, rounded UP. ValueError if requests < 0, peak_factor < 1 or seconds < 0.
    raise NotImplementedError("concurrency")


def max_requests_within_budget(budget_per_day: float, w: Workload, p: Prices) -> int:
    """Whole requests a day the budget pays for (requests_per_day in ``w`` is ignored)."""
    # TODO: floor(budget / cost_per_request). ValueError when a request costs nothing.
    raise NotImplementedError("max_requests_within_budget")
