"""Summarise a JMeter results file (JTL, CSV) the way JMeter's HTML dashboard does.

Reference solution for the lesson "Performance metrics and percentiles" (Track K).
``rows`` are the dicts ``csv.DictReader`` gives for a CSV JTL: strings such as ``timeStamp`` (epoch ms when
the sample started), ``elapsed`` (ms), ``label``, ``responseCode`` and ``success`` (``"true"``/``"false"``).
"""

from __future__ import annotations

from fundamentals.metrics_percentiles import dashboard_percentile


def _stats(rows: list[dict], percentiles: tuple[float, ...]) -> dict:
    elapsed = [int(r["elapsed"]) for r in rows]
    errors = sum(1 for r in rows if r["success"] != "true")
    start = min(int(r["timeStamp"]) for r in rows)
    end = max(int(r["timeStamp"]) + int(r["elapsed"]) for r in rows)
    duration_s = (end - start) / 1000
    out = {
        "samples": len(rows),
        "errors": errors,
        "error_pct": 100 * errors / len(rows),
        "mean_ms": sum(elapsed) / len(elapsed),
        "min_ms": min(elapsed),
        "max_ms": max(elapsed),
        "median_ms": dashboard_percentile(elapsed, 50),
        "throughput_per_s": len(rows) / duration_s if duration_s > 0 else 0.0,
    }
    for p in percentiles:
        out[f"p{p:g}_ms"] = dashboard_percentile(elapsed, p)
    return out


def summarise(rows: list[dict], percentiles: tuple[float, ...] = (90, 95, 99)) -> dict[str, dict]:
    if not rows:
        raise ValueError("no samples")
    labels = sorted({r["label"] for r in rows})
    summary = {label: _stats([r for r in rows if r["label"] == label], percentiles) for label in labels}
    summary["Total"] = _stats(rows, percentiles)
    return summary


def share_slower_than_mean(values: list[float]) -> float:
    if not values:
        raise ValueError("no values")
    mean = sum(values) / len(values)
    return sum(1 for v in values if v > mean) / len(values)
