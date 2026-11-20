"""EXERCISE - Map findings to the OWASP API Security Top 10:2023, and see which risks you have no evidence for.

Source: https://owasp.org/API-Security/editions/2023/en/0x11-t10/ (ten risks, API1..API10). The practice portal
(``support/sandpay_vuln.py``) has 17 flaw ids. Most belong to one API risk; a few belong to two; several belong
to none, because the 2023 list has no category for injection, cross-site scripting, CSRF or logging (the 2019
list's API8 Injection and API10 Insufficient Logging & Monitoring were dropped).

Decide each mapping from the "Is the API Vulnerable?" text of the risk pages, not from the flaw's name.
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
FLAW_RISKS: dict[str, tuple[str, ...]] = {}  # TODO: one entry for each of the 17 flaw ids in sandpay_vuln.FLAWS


def _number(risk: str) -> int:
    return int(risk.split(":")[0].removeprefix("API"))


def risks_for_flaw(flaw: str) -> list[str]:
    """The API risks a flaw belongs to, best fit first; ``[]`` when the 2023 list has no category for it.

    Raise ``ValueError`` for a flaw id the practice portal does not have.
    """
    raise NotImplementedError("TODO: implement risks_for_flaw")


def group_by_risk(flaws: list[str]) -> dict[str, list[str]]:
    """``{risk id: [flaw ids]}`` for the flaws given, risks in API1..API10 order, flaws in input order.

    A flaw appears under every risk it belongs to. Risks without a flaw are left out, and so are flaws with
    no category.
    """
    raise NotImplementedError("TODO: implement group_by_risk")


def untested_risks(flaws: list[str]) -> list[str]:
    """The ids of the ten risks that none of ``flaws`` covers, in API1..API10 order - the blind spots."""
    raise NotImplementedError("TODO: implement untested_risks")
