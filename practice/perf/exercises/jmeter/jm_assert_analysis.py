"""Read a JMeter CSV results file (JTL) and explain its failures.

Input is the list of row dicts that ``load_tools.read_jtl`` returns: every value is a string, ``success`` is
``"true"`` or ``"false"``, and ``failureMessage`` is empty unless an assertion failed. The CSV keeps one
failure message per sample - the first failing assertion's (the XML format keeps all of them).

Run: .venv/bin/python -m pytest tests/jmeter/test_jm_assert_analysis.py
"""

from __future__ import annotations

NO_MESSAGE = "(failed with no assertion message)"


def require_columns(rows: list[dict[str, str]], needed: list[str]) -> None:
    """Raises ValueError naming every column in ``needed`` that the JTL lacks; also ValueError for no rows.

    TODO: check the keys of the first row."""
    raise NotImplementedError("require_columns")


def normalise_message(message: str) -> str:
    """Strips the message and replaces each run of digits with ``<n>``, so "It took 151 milliseconds" and
    "It took 153 milliseconds" become the same failure kind.

    TODO: a regular expression for runs of digits."""
    raise NotImplementedError("normalise_message")


def failure_groups(rows: list[dict[str, str]]) -> list[tuple[str, str, int]]:
    """Failed samples counted by (label, normalised message), as (label, message, count) tuples, most frequent
    first, then by label, then by message. A failed sample with an empty message counts under ``NO_MESSAGE``.
    Call ``require_columns`` first (label, success, failureMessage).

    TODO: collections.Counter, then sort."""
    raise NotImplementedError("failure_groups")


def label_summary(rows: list[dict[str, str]]) -> dict[str, dict[str, float]]:
    """Per label: ``{"samples": n, "failures": f, "error_pct": round(100 * f / n, 2)}``.

    TODO"""
    raise NotImplementedError("label_summary")


def unexplained_failures(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Failed samples whose failureMessage is empty or blank: JMeter marked them failed (a 4xx/5xx status, a
    connection error) but no assertion says what was wrong.

    TODO"""
    raise NotImplementedError("unexplained_failures")
