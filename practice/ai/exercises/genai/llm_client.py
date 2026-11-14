"""A small client wrapper around a chat-style LLM: retries with backoff, and token and cost accounting.

The wrapper takes the model client as a parameter (``llm`` - anything with a ``create(**request)`` method that
returns a reply with ``input_tokens`` and ``output_tokens``), so tests pass a ``ScriptedLLM``. ``sleep`` and
``rand`` are injected too, so the tests never wait and the jitter is predictable.

The price table used by the lesson and the tests is MADE UP - "toy-small" and "toy-large" are not real models
and the prices are not any provider's. Real prices change; read them from the provider's pricing page.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable

# Fictional prices in US dollars per million tokens: (input, output). Not any provider's real prices.
TOY_PRICES: dict[str, tuple[float, float]] = {
    "toy-small": (0.50, 2.00),
    "toy-large": (5.00, 25.00),
}

RETRYABLE_STATUSES = {429, 500, 502, 503, 504, 529}


def backoff_delay(attempt: int, base: float, cap: float, rand: Callable[[], float]) -> float:
    """Exponential backoff with "full jitter": a random delay between 0 and min(cap, base * 2**attempt).

    ``attempt`` counts retries from 0. ``rand()`` returns a float in [0, 1).
    """
    raise NotImplementedError


def is_retryable(error: Exception) -> bool:
    """True for transient errors (rate limits, overload, server errors); False for anything else.

    Uses the error's ``status`` attribute (an HTTP-style code). A 400 means the request itself is wrong, so
    sending it again cannot help; neither can 401/403/404/413.
    """
    raise NotImplementedError


def cost_usd(input_tokens: int, output_tokens: int, model: str, prices: dict[str, tuple[float, float]]) -> float:
    """Cost of one call in dollars, from a per-million-token price table. Unknown model -> KeyError."""
    raise NotImplementedError


@dataclass
class LLMClient:
    """Calls ``llm.create`` with retries, and keeps running totals of tokens, cost and waiting time."""

    llm: Any
    model: str
    prices: dict[str, tuple[float, float]] = field(default_factory=lambda: dict(TOY_PRICES))
    max_retries: int = 4
    base: float = 0.5
    cap: float = 8.0
    max_total_wait: float = 30.0
    sleep: Callable[[float], None] = time.sleep
    rand: Callable[[], float] = random.random
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    calls: int = 0
    waits: list[float] = field(default_factory=list)

    def next_delay(self, error: Exception, attempt: int) -> float:
        """How long to wait before retry number ``attempt`` (0-based) after ``error``.

        A server hint (``retry_after``) is a minimum: wait that long plus a little jitter (up to ``base``).
        Without a hint, use exponential backoff with full jitter.
        """
        raise NotImplementedError

    def create(self, **request: Any):
        """Send ``request`` to the model, retrying transient errors; record usage and cost on success.

        - A non-retryable error is raised at once (no retry).
        - After ``max_retries`` retries, the last error is raised.
        - If the next wait would take the total waiting time over ``max_total_wait``, the error is raised
          instead of waiting (defer the work rather than retry sooner than the server asked).
        """
        # Starting draft: retries every error three times after a fixed second, ignores retry_after and
        # records no usage.
        for _ in range(3):
            try:
                return self.llm.create(**request)
            except Exception:
                self.sleep(1.0)
        return self.llm.create(**request)
