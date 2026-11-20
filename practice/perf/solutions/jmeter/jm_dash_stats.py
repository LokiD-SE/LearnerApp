"""jm_dash_ exercise 2 (reference solution): read the numbers out of a generated dashboard.

A JMeter 5.6.3 dashboard folder holds two machine-readable files:

- ``statistics.json`` - one object per sample label plus ``"Total"``: ``sampleCount``, ``errorCount``,
  ``errorPct``, ``meanResTime``, ``medianResTime``, ``minResTime``, ``maxResTime``, ``pct1ResTime``,
  ``pct2ResTime``, ``pct3ResTime``, ``throughput`` (per second), ``receivedKBytesPerSec``, ``sentKBytesPerSec``.
  The percentile keys are positional: ``pct1ResTime`` is whatever ``aggregate_rpt_pct1`` was (90 by default),
  so the caller must say which percentiles the report was generated with.
- ``content/js/dashboard.js`` - the tables, including Apdex and errors, as JSON literals inside calls such as
  ``createTable($("#apdexTable"), {...}, function(...``. They are not in statistics.json.
"""

from __future__ import annotations

import json
from pathlib import Path

FIELDS = {
    "sampleCount": "samples",
    "errorCount": "errors",
    "errorPct": "error_pct",
    "meanResTime": "mean_ms",
    "medianResTime": "median_ms",
    "minResTime": "min_ms",
    "maxResTime": "max_ms",
    "throughput": "throughput_per_s",
}
PCT_KEYS = ("pct1ResTime", "pct2ResTime", "pct3ResTime")


def percentile_name(p: float) -> str:
    """90 -> "p90_ms", 99.9 -> "p99.9_ms"."""
    return f"p{p:g}_ms"


def load_statistics(path: Path, percentiles: tuple[float, float, float] = (90, 95, 99)) -> dict[str, dict]:
    """statistics.json with readable keys: {label: {"samples": 20, ..., "p95_ms": 2.0, ...}}."""
    if len(percentiles) != 3:
        raise ValueError("a JMeter dashboard has exactly three percentiles")
    with open(path) as f:
        raw = json.load(f)
    if "Total" not in raw:
        raise ValueError(f"{path} has no 'Total' entry - is it a dashboard statistics.json?")
    out: dict[str, dict] = {}
    for label, entry in raw.items():
        row = {name: entry[key] for key, name in FIELDS.items()}
        for key, p in zip(PCT_KEYS, percentiles):
            row[percentile_name(p)] = entry[key]
        out[label] = row
    return out


def read_dashboard_table(dashboard_js: str, table_id: str) -> dict:
    """The JSON object passed to ``createTable($("#<table_id>"), ...)`` in dashboard.js."""
    marker = f'createTable($("#{table_id}"), '
    start = dashboard_js.find(marker)
    if start < 0:
        raise ValueError(f"table {table_id!r} not found in dashboard.js")
    obj, _ = json.JSONDecoder().raw_decode(dashboard_js, start + len(marker))
    return obj


def apdex_by_label(dashboard_js: str) -> dict[str, dict]:
    """{label: {"apdex": 0.75, "t_ms": 500, "f_ms": 1500}} for every label and "Total" (from "overall")."""
    table = read_dashboard_table(dashboard_js, "apdexTable")
    rows = [table["overall"]["data"], *(item["data"] for item in table["items"])]
    return {label: {"apdex": apdex, "t_ms": t, "f_ms": f} for apdex, t, f, label in rows}


def error_types(dashboard_js: str) -> list[tuple[str, int]]:
    """The Errors table as (type of error, number of errors), most frequent first, ties by name."""
    table = read_dashboard_table(dashboard_js, "errorsTable")
    rows = [(item["data"][0], item["data"][1]) for item in table["items"]]
    return sorted(rows, key=lambda r: (-r[1], r[0]))
