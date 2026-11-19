"""Summarise a JMeter results file (JTL, CSV) the way JMeter's HTML dashboard does.

Exercise for the lesson "Performance metrics and percentiles" (Track K). Solve metrics_percentiles.py first -
this module uses its dashboard_percentile.
Test: .venv/bin/python -m pytest tests/fundamentals/test_metrics_summary.py

``rows`` are the dicts csv.DictReader gives for a CSV JTL. Every value is a string: ``timeStamp`` (epoch ms
when the sample started), ``elapsed`` (ms), ``label``, ``responseCode``, ``success`` ("true" / "false").
"""

from __future__ import annotations

from fundamentals.metrics_percentiles import dashboard_percentile  # noqa: F401 - you will need it


def summarise(rows: list[dict], percentiles: tuple[float, ...] = (90, 95, 99)) -> dict[str, dict]:
    """TODO: one entry per label plus "Total" (all rows). Raise ValueError for no rows. Each entry has:

    samples, errors (success != "true"), error_pct (0-100), mean_ms, min_ms, max_ms (ints from elapsed),
    median_ms and one f"p{p:g}_ms" per requested percentile (dashboard_percentile), and throughput_per_s:
    samples / seconds from the earliest timeStamp to the latest timeStamp + elapsed - JMeter's formula,
    "from the start of the first sample to the end of the last sample". If that span is 0, use 0.0.
    """
    raise NotImplementedError("summarise")


def share_slower_than_mean(values: list[float]) -> float:
    """TODO: the fraction (0-1) of values strictly greater than their mean. ValueError for no values."""
    raise NotImplementedError("share_slower_than_mean")
