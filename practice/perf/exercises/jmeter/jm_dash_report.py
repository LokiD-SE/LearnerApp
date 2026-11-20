"""jm_dash_ exercise 1 : configure and build the dashboard command line.

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

from pathlib import Path

PREFIX = "jmeter.reportgenerator."
PERCENTILE_PROPS = ("aggregate_rpt_pct1", "aggregate_rpt_pct2", "aggregate_rpt_pct3")


def report_properties(
    satisfied_ms: int = 500,
    tolerated_ms: int = 1500,
    percentiles: tuple[float, float, float] = (90, 95, 99),
    title: str | None = None,
    sample_filter: str | None = None,
    per_transaction: dict[str, tuple[int, int]] | None = None,
) -> dict[str, str]:
    """The JMeter properties (name -> value, both str) for a dashboard with these settings.

    TODO:
    - Always set the two Apdex thresholds and the three percentile properties (a percentile 95.0 is written "95",
      99.9 as "99.9" - the format spec ``g`` does that).
    - Set report_title, sample_filter and apdex_per_transaction only when given. apdex_per_transaction is
      ``name:satisfied|tolerated;`` for each entry, joined with nothing in between.
    - ValueError when: satisfied is not a positive int below tolerated (also per transaction); there are not
      exactly three percentiles, strictly increasing, each between 0 and 100 (exclusive); sample_filter is not a
      valid regex; a per-transaction name is empty or contains ';' or '|'.
    """
    raise NotImplementedError("TODO: build the report properties")


def report_command(jmeter: Path, jtl: Path, out_dir: Path, props: dict[str, str]) -> list[str]:
    """``[jmeter, "-g", jtl, "-o", out_dir, "-Jname=value" ...]`` (properties sorted by name), all strings.

    TODO: FileNotFoundError if the JTL is missing; FileExistsError if out_dir exists and is not empty - JMeter
    refuses such a folder, and failing before the JVM starts gives a clearer CI log. A missing or empty out_dir
    is fine.
    """
    raise NotImplementedError("TODO: build the jmeter -g command line")
