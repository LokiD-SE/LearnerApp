"""Apdex - the Apdex Alliance's satisfaction index, as JMeter's HTML dashboard computes it.

Reference solution for the lesson "Performance metrics and percentiles" (Track K).
Apdex Technical Specification v1.1: Apdex = (satisfied + tolerating / 2) / total samples; satisfied is
0..T, tolerating is above T up to F, frustrated is above F. JMeter's ``ApdexSummaryConsumer`` counts a sample
as satisfied when ``elapsed <= T``, tolerating when ``elapsed <= F``, and counts a failed sample in the
total but in neither zone - so it is frustrated however fast it was. JMeter's defaults are T=500 ms and
F=1500 ms; the specification sets F = 4T.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal


def classify(elapsed_ms: float, success: bool, t_ms: float, f_ms: float) -> str:
    if not success:
        return "frustrated"
    if elapsed_ms <= t_ms:
        return "satisfied"
    if elapsed_ms <= f_ms:
        return "tolerating"
    return "frustrated"


def apdex(samples: Iterable[tuple[float, bool]], t_ms: float = 500, f_ms: float = 1500) -> float:
    if not 0 < t_ms <= f_ms:
        raise ValueError("thresholds must satisfy 0 < T <= F")
    zones = [classify(e, s, t_ms, f_ms) for e, s in samples]
    if not zones:
        raise ValueError("no samples")
    return (zones.count("satisfied") + zones.count("tolerating") / 2) / len(zones)


def apdex_by_label(rows: list[dict], t_ms: float = 500, f_ms: float = 1500) -> dict[str, float]:
    def samples(rs: list[dict]) -> list[tuple[float, bool]]:
        return [(int(r["elapsed"]), r["success"] == "true") for r in rs]

    result = {label: apdex(samples([r for r in rows if r["label"] == label]), t_ms, f_ms)
              for label in sorted({r["label"] for r in rows})}
    result["Total"] = apdex(samples(rows), t_ms, f_ms)
    return result


def uniform_output(score: float | None, samples: int, t_seconds: float) -> str:
    if t_seconds < 0.1:
        raise ValueError("the specification sets T in seconds, to a tenth of a second at the finest")
    t = f"{t_seconds:.1f}" if t_seconds < 10 else f"{t_seconds:.0f}"
    if samples == 0 or score is None:
        return f"NS [{t}]"
    value = Decimal(repr(score)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{value} [{t}]" + ("*" if samples < 100 else "")


def rating(score: float) -> str:
    value = Decimal(repr(score)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if value >= Decimal("0.94"):
        return "Excellent"
    if value >= Decimal("0.85"):
        return "Good"
    if value >= Decimal("0.70"):
        return "Fair"
    if value >= Decimal("0.50"):
        return "Poor"
    return "Unacceptable"
