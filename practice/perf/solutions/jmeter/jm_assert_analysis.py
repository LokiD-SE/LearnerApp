"""Read a JMeter CSV results file (JTL) and explain its failures - reference solution.

Input is the list of row dicts that ``load_tools.read_jtl`` returns: every value is a string, ``success`` is
``"true"`` or ``"false"``, and ``failureMessage`` is empty unless an assertion failed. The CSV keeps one
failure message per sample - the first failing assertion's (the XML format keeps all of them).
"""

from __future__ import annotations

import re
from collections import Counter

NO_MESSAGE = "(failed with no assertion message)"
_NUMBER = re.compile(r"\d+")


def require_columns(rows: list[dict[str, str]], needed: list[str]) -> None:
    """Raises ValueError naming every column in ``needed`` that the JTL lacks (check the save-service settings)."""
    if not rows:
        raise ValueError("the JTL has no samples")
    missing = [c for c in needed if c not in rows[0]]
    if missing:
        raise ValueError(f"the JTL lacks columns {missing}; enable them in the save service before the run")


def normalise_message(message: str) -> str:
    """Strips the message and replaces each run of digits with ``<n>`` so messages that differ only in numbers
    group together: "It took 151 milliseconds" and "It took 153 milliseconds" are one failure kind."""
    return _NUMBER.sub("<n>", message.strip())


def failure_groups(rows: list[dict[str, str]]) -> list[tuple[str, str, int]]:
    """Failed samples counted by (label, normalised message), most frequent first, then by label and message.
    A failed sample with an empty message is grouped under ``NO_MESSAGE``."""
    require_columns(rows, ["label", "success", "failureMessage"])
    counts = Counter(
        (r["label"], normalise_message(r["failureMessage"]) or NO_MESSAGE) for r in rows if r["success"] == "false"
    )
    return sorted(((label, msg, n) for (label, msg), n in counts.items()), key=lambda g: (-g[2], g[0], g[1]))


def label_summary(rows: list[dict[str, str]]) -> dict[str, dict[str, float]]:
    """Per label: ``samples``, ``failures`` and ``error_pct`` (failures / samples x 100, rounded to 2 places)."""
    require_columns(rows, ["label", "success"])
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        s = out.setdefault(r["label"], {"samples": 0, "failures": 0, "error_pct": 0.0})
        s["samples"] += 1
        s["failures"] += r["success"] == "false"
    for s in out.values():
        s["error_pct"] = round(100 * s["failures"] / s["samples"], 2)
    return out


def unexplained_failures(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Failed samples that carry no failure message: JMeter marked them failed (for example a 4xx/5xx status or a
    connection error) but no assertion says what was wrong - a sign the plan lacks an assertion there."""
    require_columns(rows, ["success", "failureMessage"])
    return [r for r in rows if r["success"] == "false" and not r["failureMessage"].strip()]
