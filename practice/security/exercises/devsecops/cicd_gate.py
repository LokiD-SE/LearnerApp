"""A gate that reads several scanners at once (CI/CD lesson).

Exercise - fill in the TODOs; ``tests/devsecops/test_cicd_gate.py`` checks your work.

Three scanners hand the gate their alerts in three vocabularies (``VOCABULARY``): ZAP says Informational/Low/Medium/High,
an SCA tool says None/Low/Medium/High/Critical (the CVSS qualitative ratings) and an invented in-house SAST tool says
note/warning/error. The gate has one scale, ``SEVERITIES`` in ``support/cicd_fixture.py``, lowest first.

Exit codes in ``enforce`` mode: 0 pass, 1 a new alert at or above ``block_at``, 2 a scan did not finish. A finding
wins over an unfinished scan. ``report`` mode never fails the run (use it for the nightly scan).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from cicd_fixture import SEVERITIES, Alert, Report

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
    baselined: list[Alert] = field(default_factory=list)  # known and the acceptance is still valid
    expired: list[Alert] = field(default_factory=list)  # known, but the acceptance ran out (counted as new too)
    reported: list[Alert] = field(default_factory=list)  # new, below the threshold
    incomplete: list[str] = field(default_factory=list)  # expected tools whose scan is missing or unfinished


def normalise_severity(tool: str, raw: str) -> str:
    """The gate's word for ``raw`` as ``tool`` says it.

    TODO: look the tool up in ``VOCABULARY`` and the word up in that tool's table, ignoring letter case and
    surrounding spaces. An unknown tool or an unknown word is a ``ValueError`` - a typo must never become a pass.
    """
    raise NotImplementedError("normalise_severity")


def decide(
    reports: list[Report],
    expected_tools: list[str],
    policy: dict[str, str],
    baseline: dict[str, str | None],
    today: datetime.date,
) -> Decision:
    """Evaluate ``reports`` against ``policy`` (``{"mode": ..., "block_at": ...}``) and ``baseline`` as of ``today``.

    ``baseline`` maps an alert id to an ISO expiry date (``"2026-12-31"``) or ``None`` for no expiry.

    TODO:
      1. ``policy["mode"]`` must be in ``MODES`` and ``policy["block_at"]`` in ``SEVERITIES``, else ``ValueError``.
         Normalise EVERY alert's severity first (so an unknown word raises even in report mode).
      2. ``incomplete`` = sorted expected tools that have no report with ``complete=True``.
      3. An alert whose id is in ``baseline`` is ``baselined`` if its expiry is ``None`` or on/after ``today``;
         otherwise it is ``expired`` AND treated as new. Other alerts are new.
      4. New alerts at or above ``block_at`` are ``blocking`` (most severe first, then by id); the rest are
         ``reported`` (by id). ``baselined`` and ``expired`` are sorted by id.
      5. ``exit_code``: report mode 0; enforce mode 1 if anything blocks, else 2 if anything is incomplete, else 0.
    """
    raise NotImplementedError("decide")
