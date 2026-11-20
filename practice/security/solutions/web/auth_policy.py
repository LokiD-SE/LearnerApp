"""Passwords and password policies checked against NIST SP 800-63B-4 (the SP 800-63-4 suite).

Two jobs a tester gets:

- ``check_password`` - would a verifier that follows SP 800-63B-4 accept this password? It counts Unicode code
  points after NFC normalisation, applies the minimum length (15 for single-factor use, 8 when the password is
  only one factor of MFA), compares the WHOLE password against a blocklist and context words, and imposes no
  composition rules.
- ``audit_policy`` - does a written password policy (from a spec or a ticket) contradict SP 800-63B-4? Each
  finding names whether it breaks a SHALL / SHALL NOT or a SHOULD.

What "derivatives" of context words means is left to the implementer by the guideline; this checker only
rejects exact (case-insensitive) matches and says so.
"""

from __future__ import annotations

import unicodedata

MIN_SINGLE_FACTOR = 15
MIN_MULTI_FACTOR = 8
RECOMMENDED_MAX_AT_LEAST = 64


def check_password(password: str, *, single_factor: bool = True, blocklist: frozenset[str] | set[str] = frozenset(),
                   context_words: tuple[str, ...] | list[str] = (), max_length: int = RECOMMENDED_MAX_AT_LEAST) -> list[str]:
    """Returns the reasons a SP 800-63B-4 verifier would reject ``password`` (empty list: acceptable).

    Codes: ``too-short``, ``too-long`` (beyond the verifier's own ``max_length``), ``blocklisted``,
    ``context-word``. ``max_length`` below 64 is refused (ValueError) because the guideline says verifiers
    SHOULD permit at least 64 characters.
    """
    if max_length < RECOMMENDED_MAX_AT_LEAST:
        raise ValueError(f"max_length must be at least {RECOMMENDED_MAX_AT_LEAST} (SP 800-63B-4: SHOULD permit 64)")
    normalised = unicodedata.normalize("NFC", password)
    length = len(normalised)  # code points, not bytes
    reasons = []
    minimum = MIN_SINGLE_FACTOR if single_factor else MIN_MULTI_FACTOR
    if length < minimum:
        reasons.append("too-short")
    if length > max_length:
        reasons.append("too-long")
    folded = normalised.casefold()
    if folded in {unicodedata.normalize("NFC", w).casefold() for w in blocklist}:
        reasons.append("blocklisted")
    if folded in {unicodedata.normalize("NFC", w).casefold() for w in context_words if w}:
        reasons.append("context-word")
    return reasons


def audit_policy(policy: dict) -> list[tuple[str, str]]:
    """Checks a password policy description against SP 800-63B-4 and returns ``(code, level)`` pairs, sorted.

    ``policy`` keys (all optional except ``min_length``): ``single_factor`` (bool, default True),
    ``min_length`` (int), ``max_length`` (int or None for no limit), ``composition_rules`` (bool),
    ``expiry_days`` (int or None), ``blocklist`` (bool), ``hints`` (bool), ``security_questions`` (bool),
    ``truncates`` (bool).

    Levels: ``SHALL`` for SHALL / SHALL NOT requirements, ``SHOULD`` for recommendations.
    """
    findings = []
    single = policy.get("single_factor", True)
    minimum = MIN_SINGLE_FACTOR if single else MIN_MULTI_FACTOR
    if policy["min_length"] < minimum:
        findings.append((f"min-length-below-{minimum}", "SHALL"))
    max_length = policy.get("max_length")
    if max_length is not None and max_length < RECOMMENDED_MAX_AT_LEAST:
        findings.append(("max-length-below-64", "SHOULD"))
    if policy.get("composition_rules"):
        findings.append(("composition-rules", "SHALL"))
    if policy.get("expiry_days"):
        findings.append(("periodic-expiry", "SHALL"))
    if not policy.get("blocklist", False):
        findings.append(("no-blocklist", "SHALL"))
    if policy.get("hints"):
        findings.append(("hints-allowed", "SHALL"))
    if policy.get("security_questions"):
        findings.append(("security-questions", "SHALL"))
    if policy.get("truncates"):
        findings.append(("truncation", "SHALL"))
    return sorted(findings)
