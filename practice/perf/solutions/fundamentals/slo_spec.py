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


_TRANSACTION = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/\S*)")
_PERCENTILE = re.compile(r"\bp(\d+(?:\.\d+)?)\b|(\d+(?:\.\d+)?)\s*%\s+of\b", re.I)
_THRESHOLD = re.compile(r"(?:<=?|under|within|less than|below)\s*(\d+(?:\.\d+)?)\s*(ms|s)\b", re.I)
_ERROR = re.compile(r"\berror rate\b.*?(?:<=?|under|below|less than)\s*(\d+(?:\.\d+)?)\s*%", re.I)
_LOAD = re.compile(r"\bat\s+(\d+(?:\.\d+)?)\s*(req/s|requests per second|rps|concurrent users|users)\b", re.I)
_AVERAGE = re.compile(r"\b(average|mean)\b", re.I)
_ABSOLUTE = re.compile(r"\b(all requests|every request|always|never)\b", re.I)


def parse_requirement(text: str) -> Requirement:
    """Returns the requirement, or raises UntestableRequirement with every reason code that applies."""
    reasons: list[str] = []
    tx = _TRANSACTION.search(text)
    if not tx:
        reasons.append("no-transaction")
    is_error = re.search(r"\berror rate\b", text, re.I) is not None
    pct = _PERCENTILE.search(text) if not is_error else None
    percentile = float(pct.group(1) or pct.group(2)) if pct else None
    threshold_ms = max_error = None
    if is_error:
        m = _ERROR.search(text)
        if m:
            max_error = float(m.group(1))
        else:
            reasons.append("no-threshold")
    else:
        m = _THRESHOLD.search(text)
        if m:
            threshold_ms = float(m.group(1)) * (1000 if m.group(2).lower() == "s" else 1)
        else:
            reasons.append("no-threshold")
        if _AVERAGE.search(text):
            reasons.append("average")
        elif percentile is None and m:
            reasons.append("no-percentile")
    if _ABSOLUTE.search(text) or (percentile is not None and percentile >= 100):
        reasons.append("absolute")
    load = _LOAD.search(text)
    if not load:
        reasons.append("no-load")
    if reasons:
        raise UntestableRequirement(text, reasons)
    unit = "req/s" if load.group(2).lower() in ("req/s", "requests per second", "rps") else "users"
    return Requirement(
        kind="errors" if is_error else "latency",
        transaction=f"{tx.group(1)} {tx.group(2)}",
        load=float(load.group(1)),
        load_unit=unit,
        percentile=percentile,
        threshold_ms=threshold_ms,
        max_error_percent=max_error,
    )


def review(texts: list[str]) -> dict[str, Requirement | list[str]]:
    """Maps each text to its Requirement, or to its reason codes when it is not testable."""
    out: dict[str, Requirement | list[str]] = {}
    for text in texts:
        try:
            out[text] = parse_requirement(text)
        except UntestableRequirement as e:
            out[text] = e.reasons
    return out
