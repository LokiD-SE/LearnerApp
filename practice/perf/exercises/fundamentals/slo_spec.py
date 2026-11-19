"""Exercise slo_spec: turn performance requirements into testable criteria - or say why they are not testable.

A testable latency or error requirement names, as Google's SRE book puts it for SLOs, "how they're measured and
the conditions under which they're valid": which transaction, which percentile (not an average), what
threshold, and at what load. This module accepts requirements written in two styles:

    p95 of POST /v1/payments < 300 ms at 50 req/s
    99% of GET /v1/payments complete in under 0.2 s at 40 req/s
    error rate of POST /v1/payments below 0.5% at 50 req/s
    p99 of GET /v1/payments/{id} <= 250 ms at 200 concurrent users

and rejects the rest with reason codes:

| code             | meaning                                                                             |
| ---------------- | ----------------------------------------------------------------------------------- |
| ``no-transaction`` | no ``METHOD /path`` - which request is it about?                                   |
| ``no-threshold``   | no number with a unit (``ms``, ``s``, or ``%`` for an error rate) - "fast" is not one |
| ``average``        | an average or mean target - averages hide the tail; state a percentile             |
| ``no-percentile``  | a latency threshold with no percentile (``p95``, ``95% of``)                        |
| ``absolute``       | 100% / "all requests" / "always" - an absolute target no run can prove             |
| ``no-load``        | no load condition (``at 50 req/s`` or ``at 200 concurrent users``)                 |
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Requirement:
    kind: str  # "latency" or "errors"
    transaction: str  # "POST /v1/payments"
    load: float  # 50.0
    load_unit: str  # "req/s" or "users"
    percentile: float | None = None  # latency only, e.g. 95.0
    threshold_ms: float | None = None  # latency only
    max_error_percent: float | None = None  # errors only


class UntestableRequirement(ValueError):
    def __init__(self, text: str, reasons: list[str]):
        super().__init__(f"{text!r} is not testable: {', '.join(reasons)}")
        self.text = text
        self.reasons = reasons


def parse_requirement(text: str) -> Requirement:
    """Returns the requirement, or raises UntestableRequirement with every reason code that applies.

    TODO:
    - Find the transaction (``METHOD /path``), the percentile (``p95`` or ``95% of``), the threshold
      (``< 300 ms``, ``<= 250 ms``, ``under 0.2 s``, ``within 50 ms`` - convert seconds to ms), the load
      (``at 50 req/s``, ``at 200 concurrent users``) and, for ``error rate`` texts, the maximum error percent.
      Regular expressions (``re``) are the simplest tool; match case-insensitively.
    - Collect EVERY reason that applies (see the table above) before raising - a reviewer wants the full
      list, not the first problem.
    - An average/mean target reports ``average`` (not also ``no-percentile``); a percentile of 100 or the
      words "all requests", "every request", "always" or "never" report ``absolute``.
    - Error-rate texts have no percentile; their threshold is the ``%`` number after below/under/<.
    """
    raise NotImplementedError("parse_requirement: see the docstring")


def review(texts: list[str]) -> dict[str, Requirement | list[str]]:
    """Maps each text to its Requirement, or to its reason codes when it is not testable.

    TODO: call parse_requirement for each text and catch UntestableRequirement.
    """
    raise NotImplementedError("review")
