"""Tracing model calls with the OpenTelemetry GenAI attribute names, latency percentiles and a release gate.

Running example: SandPay's merchant-support assistant. Every model call becomes a span an on-call engineer
can search; every release candidate is compared with the current release on a golden set before it ships.

- ``Tracer`` / ``traced_chat`` - a tiny in-memory tracer (no OpenTelemetry SDK is installed) that records
  spans named and attributed as the OpenTelemetry GenAI semantic conventions describe for client inference
  (status "Development" - names may still change): span name ``"{gen_ai.operation.name} {gen_ai.request.model}"``,
  ``gen_ai.operation.name``, ``gen_ai.provider.name``, ``gen_ai.request.model``, ``gen_ai.request.max_tokens``,
  ``gen_ai.request.temperature``, ``gen_ai.usage.input_tokens``, ``gen_ai.usage.output_tokens``,
  ``gen_ai.response.finish_reasons`` and, on failure, ``error.type``. Prompt and reply text are NOT recorded:
  in the conventions, message content is opt-in.
- ``time_to_first_chunk`` - measured from the start of the call to the first streamed chunk.
- ``percentile`` - the nearest-rank method.
- ``release_gate`` - compares a candidate's golden-set run with the baseline's.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable


@dataclass
class Span:
    name: str
    start: float
    end: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "UNSET"  # "UNSET" | "ERROR"

    @property
    def duration(self) -> float:
        assert self.end is not None, "span not ended"
        return self.end - self.start


class Tracer:
    """Collects finished spans in ``spans``; the clock is injected."""

    def __init__(self, clock: Callable[[], float]):
        self.clock = clock
        self.spans: list[Span] = []

    def start(self, name: str, attributes: dict[str, Any]) -> Span:
        return Span(name, self.clock(), attributes=dict(attributes))

    def end(self, span: Span) -> None:
        span.end = self.clock()
        self.spans.append(span)


def traced_chat(tracer: Tracer, llm: Any, *, provider: str, model: str, **request: Any) -> Any:
    """Call ``llm.create(**request)`` inside a span and return the reply.

    Attributes set at the start: operation name ``"chat"``, provider, request model, and - when present in
    the request - max_tokens and temperature. After a reply: input and output token counts and
    ``finish_reasons`` as a one-element list holding the reply's ``stop_reason``. On an exception: status
    ``"ERROR"``, ``error.type`` = the exception's class name, the span is still ended, and the exception is
    re-raised unchanged.
    """
    raise NotImplementedError("TODO: traced_chat - see the docstring and tests/production/test_ops_telemetry.py")


def time_to_first_chunk(start: float, chunks: Iterable[str], clock: Callable[[], float]) -> tuple[float | None, float, str]:
    """Consume a stream; return ``(ttfc, total, text)``.

    ``ttfc`` is seconds from ``start`` to the first non-empty chunk (None if no chunk arrived); ``total``
    is seconds from ``start`` to the end of the stream.
    """
    raise NotImplementedError("TODO: time_to_first_chunk - see the docstring and tests/production/test_ops_telemetry.py")


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile: the smallest value with at least p% of the values at or below it."""
    raise NotImplementedError("TODO: percentile - see the docstring and tests/production/test_ops_telemetry.py")


@dataclass
class RunSummary:
    """One golden-set run: per-case pass/fail, latencies in seconds, and total cost in dollars."""

    passed: dict[str, bool]
    latencies: list[float]
    cost: float


def release_gate(
    baseline: RunSummary,
    candidate: RunSummary,
    *,
    max_pass_rate_drop: float,
    p95_budget: float,
    max_cost_increase: float,
) -> list[str]:
    """Return the reasons to block the release (empty list = ship).

    - ``"pass rate a -> b"`` if the candidate's pass rate is more than ``max_pass_rate_drop`` below the
      baseline's (rates rounded to 3 decimals in the message);
    - ``"regressed: <id>, ..."`` for cases that passed in the baseline and fail in the candidate (sorted),
      whatever the overall rate;
    - ``"p95 latency x > budget"`` if the candidate's p95 exceeds ``p95_budget``;
    - ``"cost +n%"`` if the candidate costs more than ``max_cost_increase`` (a fraction) above baseline.
    The two runs must cover the same case ids; otherwise raise ValueError.
    """
    raise NotImplementedError("TODO: release_gate - see the docstring and tests/production/test_ops_telemetry.py")
