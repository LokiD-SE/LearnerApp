"""jm_dash_ exercise 2: read the numbers out of a generated dashboard.

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
    """statistics.json with readable keys: {label: {"samples": 20, ..., "p95_ms": 2.0, ...}}.

    TODO: for every label (including "Total") rename the FIELDS keys, and map pct1/2/3ResTime to
    percentile_name(p) for the given percentiles, in order. ValueError if there are not exactly three
    percentiles, or the file has no "Total" entry.
    """
    raise NotImplementedError("TODO: load statistics.json")


def read_dashboard_table(dashboard_js: str, table_id: str) -> dict:
    """The JSON object passed to ``createTable($("#<table_id>"), ...)`` in dashboard.js.

    TODO: find the marker, then parse the JSON object that starts right after it - json.JSONDecoder().raw_decode
    parses one value starting at an index and ignores what follows. ValueError if the table is not there.
    """
    raise NotImplementedError("TODO: extract a table from dashboard.js")


def apdex_by_label(dashboard_js: str) -> dict[str, dict]:
    """{label: {"apdex": 0.75, "t_ms": 500, "f_ms": 1500}} for every label and "Total".

    TODO: each row's "data" is [apdex, T, F, label]; "Total" is the table's "overall" row, the labels are its
    "items".
    """
    raise NotImplementedError("TODO: read the Apdex table")


def error_types(dashboard_js: str) -> list[tuple[str, int]]:
    """The Errors table ("errorsTable") as (type of error, number of errors), most frequent first, ties by name.

    TODO: each item's "data" is [type of error, number of errors, % in errors, % in all samples].
    """
    raise NotImplementedError("TODO: read the Errors table")
