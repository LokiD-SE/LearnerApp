"""Retries with backoff and jitter, Retry-After, a time budget, and fallback between models.

Running example: SandPay's merchant-support assistant calls a hosted model. Rate limits (429), overloads
(503/529) and the occasional 500 are normal; a broken request (400) or a spent monthly budget is not
something a retry can fix.

- ``backoff_delay`` - "Full Jitter", as the AWS Architecture Blog post *Exponential Backoff And Jitter* names it:
  a uniform random wait between 0 and the capped exponential backoff ``min(cap, base * 2 ** attempt)``.
- ``call_with_retries`` - retries only retryable errors, waits at least ``retry_after`` when the error
  carries one (Anthropic Rate limits: "Wait at least the number of seconds in the retry-after header"),
  and gives up when the next wait would cross the deadline.
- ``FallbackChain`` - tries models in order; moves to the next model only when the current one is
  unavailable (retries used up, or a spend cap), never for a bad request.

Sleeping and the clock are injected, so tests never wait.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable

from llm_fake import LLMError


class SpendCapError(LLMError):
    """A 429 with no Retry-After: the organisation's spend cap is reached. Retrying fails until it resets."""

    status = 429
    retryable = False


class RetryBudgetExceeded(Exception):
    """The next wait would end after the deadline; ``last_error`` is what the final attempt raised."""

    def __init__(self, last_error: Exception, attempts: int):
        super().__init__(f"gave up after {attempts} attempt(s): {last_error}")
        self.last_error = last_error
        self.attempts = attempts


def is_retryable(error: Exception) -> bool:
    """True for errors a later identical request can succeed on: rate limits and transient server errors."""
    return isinstance(error, LLMError) and bool(getattr(error, "retryable", False))


def backoff_delay(attempt: int, base: float, cap: float, rng: random.Random) -> float:
    """Full jitter: a uniform random wait between 0 and min(cap, base * 2**attempt). ``attempt`` starts at 0."""
    if attempt < 0:
        raise ValueError("attempt must be >= 0")
    return rng.uniform(0, min(cap, base * 2**attempt))


@dataclass
class Attempt:
    number: int  # 1-based
    error: str | None  # the error class name, or None for success
    waited: float  # seconds slept after this attempt (0 for the last one)


@dataclass
class RetryResult:
    value: Any
    attempts: list[Attempt] = field(default_factory=list)


def call_with_retries(
    fn: Callable[[], Any],
    *,
    max_attempts: int = 3,
    base: float = 0.5,
    cap: float = 8.0,
    deadline: float | None = None,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
    rng: random.Random,
) -> RetryResult:
    """Call ``fn`` until it succeeds, a non-retryable error happens, attempts run out or the deadline is near.

    - Non-retryable errors are raised at once, unchanged.
    - After a retryable error the wait is ``max(retry_after, backoff_delay(...))`` - never shorter than the
      server asked for.
    - If ``clock() + wait`` would pass ``deadline``, raise ``RetryBudgetExceeded`` instead of sleeping.
    - When attempts run out, the last error is raised unchanged.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    attempts: list[Attempt] = []
    for number in range(1, max_attempts + 1):
        try:
            value = fn()
        except Exception as error:  # noqa: BLE001 - classified below
            if not is_retryable(error):
                raise
            if number == max_attempts:
                attempts.append(Attempt(number, type(error).__name__, 0.0))
                raise
            wait = max(float(getattr(error, "retry_after", 0.0) or 0.0), backoff_delay(number - 1, base, cap, rng))
            if deadline is not None and clock() + wait > deadline:
                attempts.append(Attempt(number, type(error).__name__, 0.0))
                raise RetryBudgetExceeded(error, number) from error
            attempts.append(Attempt(number, type(error).__name__, wait))
            sleep(wait)
            continue
        attempts.append(Attempt(number, None, 0.0))
        return RetryResult(value, attempts)
    raise AssertionError("unreachable")


@dataclass
class FallbackResult:
    reply: Any
    model: str
    tried: list[tuple[str, str]]  # (model, outcome) for every model tried, in order


class FallbackChain:
    """Try each ``(model_name, client)`` in order with ``call_with_retries``.

    Move to the next model when the current one is unavailable: its retries ran out on a retryable
    error, the retry budget ran out, or it hit a ``SpendCapError``. Any other error (a ``BadRequestError``
    - the next model would reject the same request) is raised at once. If every model is unavailable,
    raise the last model's error.
    """

    def __init__(self, models: list[tuple[str, Any]], **retry_options: Any):
        if not models:
            raise ValueError("at least one model is needed")
        self.models = models
        self.retry_options = retry_options

    def create(self, **request: Any) -> FallbackResult:
        tried: list[tuple[str, str]] = []
        last: Exception | None = None
        for name, client in self.models:
            try:
                result = call_with_retries(lambda c=client: c.create(**request), **self.retry_options)
            except (RetryBudgetExceeded, SpendCapError) as error:
                tried.append((name, type(error).__name__))
                last = error
                continue
            except Exception as error:
                if not is_retryable(error):
                    tried.append((name, type(error).__name__))
                    raise
                tried.append((name, type(error).__name__))
                last = error
                continue
            tried.append((name, "ok"))
            return FallbackResult(result.value, name, tried)
        assert last is not None
        raise last
