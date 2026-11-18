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
    _check(w)
    uncached = w.input_tokens - w.cached_input_tokens
    return (uncached * p.input + w.cached_input_tokens * p.cached_input + w.output_tokens * p.output) / 1_000_000


def daily_cost(w: Workload, p: Prices) -> float:
    """Cost per day in EUR, rounded to cents."""
    return round(cost_per_request(w, p) * w.requests_per_day, 2)


def response_seconds(ttft_seconds: float, output_tokens: int, tokens_per_second: float) -> float:
    """Time until the whole reply has streamed: first token, then the rest at the output speed."""
    if ttft_seconds < 0 or output_tokens < 0 or tokens_per_second <= 0:
        raise ValueError("ttft and output tokens must be >= 0 and tokens_per_second > 0")
    return ttft_seconds + output_tokens / tokens_per_second


def concurrency(requests_per_day: int, peak_factor: float, seconds_per_request: float) -> int:
    """Requests in flight at the peak (Little's law), rounded up to whole requests."""
    if requests_per_day < 0 or peak_factor < 1 or seconds_per_request < 0:
        raise ValueError("requests >= 0, peak_factor >= 1, seconds_per_request >= 0")
    arrivals_per_second = requests_per_day / SECONDS_PER_DAY * peak_factor
    return math.ceil(arrivals_per_second * seconds_per_request)


def max_requests_within_budget(budget_per_day: float, w: Workload, p: Prices) -> int:
    """Whole requests a day the budget pays for (requests_per_day in ``w`` is ignored)."""
    per_request = cost_per_request(w, p)
    if per_request == 0:
        raise ValueError("a request that costs nothing has no budget limit")
    return math.floor(budget_per_day / per_request)
