"""A finding is only as useful as its report: a linter for the fields, the score and the evidence."""

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
    """The CVSS qualitative severity rating scale (same for v3.1 and v4.0)."""
    if score == 0.0:
        return "None"
    if score <= 3.9:
        return "Low"
    if score <= 6.9:
        return "Medium"
    if score <= 8.9:
        return "High"
    return "Critical"


def lint_finding(finding: dict, score_of: Callable[[str], float]) -> list[str]:
    """Return the sorted, de-duplicated problem codes of a finding (an empty list means it is ready to send)."""
    problems: set[str] = set()
    for field in REQUIRED:
        if not finding.get(field):
            problems.add(f"missing:{field}")
    cwe = finding.get("cwe")
    if cwe and not CWE.fullmatch(cwe):
        problems.add("bad-cwe")
    cve = finding.get("cve")
    if cve and not CVE.fullmatch(cve):
        problems.add("bad-cve")
    cvss = finding.get("cvss") or {}
    if cvss:
        try:
            computed = score_of(cvss.get("vector", ""))
        except ValueError:
            problems.add("bad-vector")
        else:
            if cvss.get("score") != computed:
                problems.add("score-mismatch")
        reported = cvss.get("score")
        if not isinstance(reported, (int, float)) or cvss.get("rating") != qualitative(reported):
            problems.add("rating-mismatch")
    steps = finding.get("steps") or []
    if steps and len(steps) < 2:
        problems.add("steps-too-few")
    impact = finding.get("impact") or ""
    if impact and len(impact.split()) < 8:
        problems.add("impact-too-thin")
    for item in finding.get("evidence") or []:
        if not item.get("request") or not item.get("response"):
            problems.add("evidence-incomplete")
        text = f"{item.get('request', '')}\n{item.get('response', '')}"
        if BEARER.search(text) or PASSWORD.search(text):
            problems.add("secret-in-evidence")
        if CARD_LIKE.search(text):
            problems.add("card-number-in-evidence")
    return sorted(problems)
