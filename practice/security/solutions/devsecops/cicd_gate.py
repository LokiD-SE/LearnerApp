"""A gate that reads several scanners at once (CI/CD lesson).

Solution. Three steps: put every tool's severity on one scale, split the alerts into new, baselined and
expired-baseline, and turn that into an exit code that fails closed when a scan did not finish.

Exit codes in ``enforce`` mode: 0 pass, 1 a new alert at or above ``block_at``, 2 a scan did not finish. Findings
win over an unfinished scan, because they are certain. ``report`` mode never fails the run.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from cicd_fixture import SEVERITIES, Alert, Report

# Each tool's own words mapped to the gate's scale. ``sast`` is an invented in-house tool.
VOCABULARY = {
    "zap": {"informational": "info", "low": "low", "medium": "medium", "high": "high"},
    "sca": {"none": "info", "low": "low", "medium": "medium", "high": "high", "critical": "critical"},
    "sast": {"note": "low", "warning": "medium", "error": "high"},
}
MODES = ("enforce", "report")


@dataclass
class Decision:
    exit_code: int = 0
    blocking: list[Alert] = field(default_factory=list)  # new, at or above the threshold
    baselined: list[Alert] = field(default_factory=list)  # known and still accepted
    expired: list[Alert] = field(default_factory=list)  # known, but the acceptance ran out (also counted as new)
    reported: list[Alert] = field(default_factory=list)  # new, below the threshold
    incomplete: list[str] = field(default_factory=list)  # tools whose scan is missing or did not finish


def normalise_severity(tool: str, raw: str) -> str:
    """The gate's word for ``raw`` as ``tool`` says it. Unknown tool or word: ``ValueError`` (never a pass)."""
    if tool not in VOCABULARY:
        raise ValueError(f"unknown tool {tool!r}")
    table = VOCABULARY[tool]
    key = raw.strip().lower()
    if key not in table:
        raise ValueError(f"unknown {tool} severity {raw!r}")
    return table[key]


def _rank(severity: str) -> int:
    return SEVERITIES.index(severity)


def decide(
    reports: list[Report],
    expected_tools: list[str],
    policy: dict[str, str],
    baseline: dict[str, str | None],
    today: datetime.date,
) -> Decision:
    """Evaluate ``reports`` against ``policy`` and ``baseline`` as of ``today``."""
    mode = policy.get("mode")
    block_at = policy.get("block_at")
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}")
    if block_at not in SEVERITIES:
        raise ValueError(f"unknown block_at {block_at!r}")

    # Validate everything before deciding anything, so one typo cannot weaken the gate.
    normalised = [(alert, normalise_severity(alert.tool, alert.severity)) for r in reports for alert in r.alerts]

    decision = Decision()
    finished = {r.tool for r in reports if r.complete}
    decision.incomplete = sorted(t for t in expected_tools if t not in finished)

    new: list[tuple[Alert, str]] = []
    for alert, level in normalised:
        if alert.id in baseline:
            expiry = baseline[alert.id]
            if expiry is None or datetime.date.fromisoformat(expiry) >= today:
                decision.baselined.append(alert)
                continue
            decision.expired.append(alert)
        new.append((alert, level))

    threshold = _rank(block_at)
    blocking = [(a, lv) for a, lv in new if _rank(lv) >= threshold]
    decision.blocking = [a for a, lv in sorted(blocking, key=lambda p: (-_rank(p[1]), p[0].id))]
    decision.reported = sorted((a for a, lv in new if _rank(lv) < threshold), key=lambda a: a.id)
    decision.baselined.sort(key=lambda a: a.id)
    decision.expired.sort(key=lambda a: a.id)

    if mode == "report":
        decision.exit_code = 0
    elif decision.blocking:
        decision.exit_code = 1
    elif decision.incomplete:
        decision.exit_code = 2
    else:
        decision.exit_code = 0
    return decision
