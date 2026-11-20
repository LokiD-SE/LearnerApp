"""jm_dash_ exercise 1 (reference solution): configure and build the dashboard command line.

JMeter generates its HTML dashboard from a CSV JTL with ``jmeter -g <log file> -o <output folder>`` (user
manual 14.3.1); the output folder "must not exist or be empty". Report settings are JMeter properties, so a CI job
passes them with ``-J`` instead of editing ``user.properties``:

- ``jmeter.reportgenerator.apdex_satisfied_threshold`` / ``apdex_tolerated_threshold`` (ms, defaults 500 / 1500);
- ``jmeter.reportgenerator.apdex_per_transaction`` - ``name:satisfied|tolerated;`` per sample name or regex;
- ``jmeter.reportgenerator.report_title`` and ``jmeter.reportgenerator.sample_filter`` (a regex of sample names to
  keep - applied before any statistics are calculated, so it changes ``Total`` too);
- ``aggregate_rpt_pct1`` .. ``aggregate_rpt_pct3`` - the three percentiles. These have NO
  ``jmeter.reportgenerator.`` prefix (they live in ``jmeter.properties``); with the prefix JMeter ignores them
  silently and keeps 90 / 95 / 99.
"""

from __future__ import annotations

import re
from pathlib import Path

PREFIX = "jmeter.reportgenerator."
PERCENTILE_PROPS = ("aggregate_rpt_pct1", "aggregate_rpt_pct2", "aggregate_rpt_pct3")


def _check_thresholds(satisfied_ms: int, tolerated_ms: int, what: str) -> None:
    if not (isinstance(satisfied_ms, int) and isinstance(tolerated_ms, int)):
        raise ValueError(f"{what}: thresholds must be whole milliseconds")
    if satisfied_ms <= 0 or tolerated_ms <= satisfied_ms:
        raise ValueError(f"{what}: need 0 < satisfied ({satisfied_ms}) < tolerated ({tolerated_ms})")


def report_properties(
    satisfied_ms: int = 500,
    tolerated_ms: int = 1500,
    percentiles: tuple[float, float, float] = (90, 95, 99),
    title: str | None = None,
    sample_filter: str | None = None,
    per_transaction: dict[str, tuple[int, int]] | None = None,
) -> dict[str, str]:
    """The JMeter properties (name -> value, both str) for a dashboard with these settings."""
    _check_thresholds(satisfied_ms, tolerated_ms, "apdex")
    if len(percentiles) != 3:
        raise ValueError("the dashboard has exactly three configurable percentiles")
    if not all(0 < p < 100 for p in percentiles) or list(percentiles) != sorted(set(percentiles)):
        raise ValueError(f"percentiles must be distinct, increasing and between 0 and 100: {percentiles}")
    props = {
        PREFIX + "apdex_satisfied_threshold": str(satisfied_ms),
        PREFIX + "apdex_tolerated_threshold": str(tolerated_ms),
    }
    for name, p in zip(PERCENTILE_PROPS, percentiles):
        props[name] = f"{p:g}"
    if title:
        props[PREFIX + "report_title"] = title
    if sample_filter:
        try:
            re.compile(sample_filter)
        except re.error as exc:
            raise ValueError(f"sample_filter is not a valid regular expression: {exc}") from exc
        props[PREFIX + "sample_filter"] = sample_filter
    if per_transaction:
        parts = []
        for name, (t, f) in per_transaction.items():
            if not name or any(c in name for c in ";|"):
                raise ValueError(f"sample name {name!r} cannot be empty or contain ';' or '|'")
            _check_thresholds(t, f, name)
            parts.append(f"{name}:{t}|{f};")
        props[PREFIX + "apdex_per_transaction"] = "".join(parts)
    return props


def report_command(jmeter: Path, jtl: Path, out_dir: Path, props: dict[str, str]) -> list[str]:
    """``[jmeter, "-g", jtl, "-o", out_dir, "-Jname=value" ...]`` (properties sorted by name).

    FileNotFoundError if the JTL is missing; FileExistsError if out_dir exists and is not empty - JMeter
    refuses such a folder, and failing before the JVM starts gives a clearer CI log.
    """
    jtl, out_dir = Path(jtl), Path(out_dir)
    if not jtl.is_file():
        raise FileNotFoundError(f"results file not found: {jtl}")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"report folder is not empty: {out_dir}")
    return [str(jmeter), "-g", str(jtl), "-o", str(out_dir), *(f"-J{k}={v}" for k, v in sorted(props.items()))]
