"""SOLUTION - Fingerprints, inline suppressions, a baseline and the gate that decides the exit code."""

from __future__ import annotations

import hashlib
import re

SEVERITIES = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
SUPPRESSION = re.compile(r"#\s*nosemgrep(?::\s*([\w.-]+(?:\s*,\s*[\w.-]+)*))?")


def fingerprint(rule_id: str, path: str, line_text: str) -> str:
    """16 hex characters that identify a finding without its line NUMBER, so inserting code above it does not
    make it look new. Whitespace in ``line_text`` is normalised first."""
    normalised = " ".join(line_text.split())
    return hashlib.sha256(f"{rule_id}:{path}:{normalised}".encode()).hexdigest()[:16]


def is_suppressed(lines: list[str], line_no: int, rule_id: str) -> bool:
    """True when ``# nosemgrep`` is on the finding's line or the line before it. A bare comment suppresses every
    rule; ``# nosemgrep: a, b`` suppresses only the rules it names."""
    for number in (line_no, line_no - 1):
        if 1 <= number <= len(lines):
            match = SUPPRESSION.search(lines[number - 1])
            if match:
                names = match.group(1)
                if names is None or rule_id in [n.strip() for n in names.split(",")]:
                    return True
    return False


def make_baseline(findings: list[dict]) -> list[str]:
    """The sorted, de-duplicated fingerprints of the findings you accept today."""
    return sorted({fingerprint(f["rule_id"], f["path"], f["text"]) for f in findings})


def gate(findings: list[dict], baseline: set[str] | list[str], fail_on: str = "HIGH") -> dict:
    """Decide the pipeline result. Each finding is ``{"rule_id", "path", "line", "severity", "text"}``.

    Returns ``{"exit_code", "blocking", "new", "known"}``: ``new`` are the findings whose fingerprint is not in
    the baseline, ``blocking`` the new ones at or above ``fail_on``, ``known`` the count already baselined.
    An unknown ``fail_on`` or an unknown finding severity raises ``ValueError`` - a typo must not open the gate.
    """
    if fail_on not in SEVERITIES:
        raise ValueError(f"unknown severity: {fail_on!r}")
    for f in findings:
        if f["severity"] not in SEVERITIES:
            raise ValueError(f"unknown severity: {f['severity']!r}")
    accepted = set(baseline)
    new = [f for f in findings if fingerprint(f["rule_id"], f["path"], f["text"]) not in accepted]
    blocking = [f for f in new if SEVERITIES[f["severity"]] >= SEVERITIES[fail_on]]
    return {"exit_code": 1 if blocking else 0, "blocking": blocking, "new": new, "known": len(findings) - len(new)}
