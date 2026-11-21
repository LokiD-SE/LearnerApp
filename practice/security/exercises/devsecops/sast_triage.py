"""EXERCISE - Fingerprints, inline suppressions, a baseline and the gate that decides the exit code.

Finding a problem is half the job; the other half is making a CI pipeline act on *new* problems only, without
being drowned by old ones and without letting a typo open the gate.
"""

from __future__ import annotations

import re

SEVERITIES = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
SUPPRESSION = re.compile(r"#\s*nosemgrep(?::\s*([\w.-]+(?:\s*,\s*[\w.-]+)*))?")


def fingerprint(rule_id: str, path: str, line_text: str) -> str:
    """16 hex characters that identify a finding WITHOUT its line number, so inserting code above it does not
    make it look new. Normalise the whitespace of ``line_text`` (``" ".join(line_text.split())``), hash
    ``f"{rule_id}:{path}:{normalised}"`` with SHA-256 and keep the first 16 hex characters."""
    raise NotImplementedError("TODO: normalise, hash, truncate")


def is_suppressed(lines: list[str], line_no: int, rule_id: str) -> bool:
    """True when a ``# nosemgrep`` comment is on the finding's line (``line_no``, numbered from 1) or on the
    line before it. A bare comment suppresses every rule; ``# nosemgrep: a, b`` suppresses only the rules it
    names. Use ``SUPPRESSION``. Line numbers outside the file are simply not checked."""
    raise NotImplementedError("TODO: look at the finding's line and the one above it")


def make_baseline(findings: list[dict]) -> list[str]:
    """The sorted, de-duplicated fingerprints of the findings you accept today (use ``f["rule_id"]``,
    ``f["path"]`` and ``f["text"]`` - the source line)."""
    raise NotImplementedError("TODO: fingerprint every finding, de-duplicate, sort")


def gate(findings: list[dict], baseline: set[str] | list[str], fail_on: str = "HIGH") -> dict:
    """Decide the pipeline result. Each finding is ``{"rule_id", "path", "line", "severity", "text"}``.

    Return ``{"exit_code", "blocking", "new", "known"}``:

    * ``new`` - findings whose fingerprint is not in the baseline;
    * ``blocking`` - the new ones whose severity is at or above ``fail_on``;
    * ``exit_code`` - 1 when anything is blocking, else 0;
    * ``known`` - how many findings were already in the baseline.

    An unknown ``fail_on`` or an unknown finding severity raises ``ValueError`` - a typo must not open the gate.
    """
    raise NotImplementedError("TODO: validate severities, split new from known, decide the exit code")
