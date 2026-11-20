"""SOLUTION - Map findings to the OWASP API Security Top 10:2023, and see which risks you have no evidence for.

Source: https://owasp.org/API-Security/editions/2023/en/0x11-t10/ (ten risks, API1..API10). The practice portal
(``support/sandpay_vuln.py``) has 17 flaw ids. Most belong to one API risk; a few belong to two; several belong
to none, because the 2023 list has no category for injection, cross-site scripting, CSRF or logging (the 2019
list's API8 Injection and API10 Insufficient Logging & Monitoring were dropped).

Rules used here (each from the risk's "Is the API Vulnerable?" text):

* the id of an object is checked per object -> API1; an individual property is read or written without a check
  -> API3 (both Excessive Data Exposure and Mass Assignment live there since 2023);
* tokens and credentials: unsigned (``alg: none``) JWTs, weakly hashed passwords, brute force without lockout
  -> API2; a missing limit on how often an operation may run -> API4 (so ``no-rate-limit`` belongs to both);
* the server fetches a user-supplied URL -> API7; stack traces and missing security headers -> API8.
"""

from __future__ import annotations

RISKS = {
    "API1:2023": "Broken Object Level Authorization",
    "API2:2023": "Broken Authentication",
    "API3:2023": "Broken Object Property Level Authorization",
    "API4:2023": "Unrestricted Resource Consumption",
    "API5:2023": "Broken Function Level Authorization",
    "API6:2023": "Unrestricted Access to Sensitive Business Flows",
    "API7:2023": "Server Side Request Forgery",
    "API8:2023": "Security Misconfiguration",
    "API9:2023": "Improper Inventory Management",
    "API10:2023": "Unsafe Consumption of APIs",
}

# flaw id -> API risks, the best fit first. An empty tuple means "no API Top 10:2023 category".
FLAW_RISKS: dict[str, tuple[str, ...]] = {
    "idor": ("API1:2023",),
    "mass-assignment": ("API3:2023",),
    "data-exposure": ("API3:2023",),
    "jwt-none": ("API2:2023",),
    "weak-hash": ("API2:2023",),
    "no-rate-limit": ("API4:2023", "API2:2023"),
    "ssrf": ("API7:2023",),
    "verbose-errors": ("API8:2023",),
    "missing-headers": ("API8:2023",),
    "sqli": (),
    "xss-reflected": (),
    "xss-stored": (),
    "csrf": (),
    "open-redirect": (),
    "path-traversal": (),
    "weak-session": (),
    "secret-logging": (),
}


def _number(risk: str) -> int:
    return int(risk.split(":")[0].removeprefix("API"))


def risks_for_flaw(flaw: str) -> list[str]:
    """The API risks a flaw belongs to, best fit first; ``[]`` when the 2023 list has no category for it.

    Raise ``ValueError`` for a flaw id the practice portal does not have.
    """
    if flaw not in FLAW_RISKS:
        raise ValueError(f"unknown flaw id: {flaw!r}")
    return list(FLAW_RISKS[flaw])


def group_by_risk(flaws: list[str]) -> dict[str, list[str]]:
    """``{risk id: [flaw ids]}`` for the flaws given, risks in API1..API10 order, flaws in input order.

    A flaw appears under every risk it belongs to. Risks without a flaw are left out, and so are flaws with
    no category.
    """
    grouped: dict[str, list[str]] = {}
    for flaw in flaws:
        for risk in risks_for_flaw(flaw):
            grouped.setdefault(risk, []).append(flaw)
    return {risk: grouped[risk] for risk in sorted(grouped, key=_number)}


def untested_risks(flaws: list[str]) -> list[str]:
    """The ids of the ten risks that none of ``flaws`` covers, in API1..API10 order - the blind spots."""
    covered = set(group_by_risk(flaws))
    return [risk for risk in sorted(RISKS, key=_number) if risk not in covered]
