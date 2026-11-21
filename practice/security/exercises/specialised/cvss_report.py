"""EXERCISE - lint a vulnerability finding before it is sent.

A finding is a dict (see ``GOOD_FINDING`` in ``support/cvss_fixture.py``). ``score_of`` is a function that takes a
CVSS vector string and returns its score, or raises ``ValueError`` for an invalid vector - the tests pass a stub, so
this module does not depend on your scorers.

* ``qualitative(score)`` - the CVSS qualitative severity rating scale: 0.0 "None", 0.1-3.9 "Low", 4.0-6.9
  "Medium", 7.0-8.9 "High", 9.0-10.0 "Critical".
* ``lint_finding(finding, score_of)`` - return the problem codes, SORTED and without repeats ([] means ready):
    - ``missing:<field>`` for each of ``REQUIRED`` that is absent or empty;
    - ``bad-cwe`` when ``cwe`` is present but is not ``CWE-`` plus 1 to 6 digits not starting with 0;
    - ``bad-cve`` when an optional ``cve`` is present but is not ``CVE-YYYY-`` plus 4 to 19 digits (the CVE Record Format pattern);
    - from ``cvss`` ({"version", "vector", "score", "rating"}): ``bad-vector`` when ``score_of`` raises ``ValueError``
      (and then do not compare scores); ``score-mismatch`` when the reported ``score`` differs from ``score_of``;
      ``rating-mismatch`` when the reported ``rating`` is not ``qualitative`` of the REPORTED score;
    - ``steps-too-few`` when ``steps`` has exactly one entry (a reader cannot repeat one step);
    - ``impact-too-thin`` when ``impact`` is present but has fewer than 8 words;
    - for each ``evidence`` item: ``evidence-incomplete`` when ``request`` or ``response`` is missing or empty;
      ``secret-in-evidence`` when the text holds a ``Bearer <token>`` of 8 or more token characters, or a
      ``password`` value, that is not ``[REDACTED]``; ``card-number-in-evidence`` when it holds a run of 13 to 19 digits.
  House rules, not standards. Never modify the finding.
"""

from __future__ import annotations

import re
from typing import Callable

REQUIRED = ("title", "affected", "cwe", "cvss", "summary", "steps", "evidence", "impact", "remediation")
CWE = re.compile(r"CWE-[1-9][0-9]{0,5}")
CVE = re.compile(r"CVE-[0-9]{4}-[0-9]{4,19}")
BEARER = re.compile(r"Bearer\s+(?!\[REDACTED\])[A-Za-z0-9._~+/=-]{8,}")
PASSWORD = re.compile(r"\"?password\"?\s*[:=]\s*\"?(?!\[REDACTED\])[^\s\",}]{3,}", re.IGNORECASE)
CARD_LIKE = re.compile(r"(?<![0-9])[0-9]{13,19}(?![0-9])")


def qualitative(score: float) -> str:
    raise NotImplementedError("TODO: implement qualitative")


def lint_finding(finding: dict, score_of: Callable[[str], float]) -> list[str]:
    raise NotImplementedError("TODO: implement lint_finding")
