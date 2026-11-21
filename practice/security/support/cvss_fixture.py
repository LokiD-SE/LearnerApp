"""Support for the cvss_ exercises (Track L, vulnerability-reporting-and-cvss).

What is here, and where each part comes from:

* ``V31_*`` / ``V4_*`` - the metric names, their allowed values and the vector order, from the FIRST specifications
  (CVSS v3.1 section 6 and CVSS v4.0 Table 23), read on 21 November 2026.
* ``interpolate`` - the CVSS v4.0 scoring step after the macro vector is known (FIRST's published algorithm: take
  the macro vector's score, then subtract the mean of the proportional distances to the next lower macro vectors).
  It is a Python port of ``cvss_score.js`` from FIRST's calculator repository (BSD-2-Clause) and uses the tables
  in ``cvss_data.py``. Base metrics and Exploit Maturity (E) only: the environmental and supplemental metrics are
  not ported. The learner writes the part before it - the six equivalence classes - in ``cvss_v4.py``.
* ``V31_PUBLISHED`` / ``V4_PUBLISHED`` - vectors and scores printed on FIRST's CVSS v4.0 examples page (it lists the
  v3.1 and the v4.0 score of each example), read on 21 November 2026. Only vectors made of base metrics (and E) are
  kept, because those are the ones these exercises score.
* ``GOOD_FINDING`` / ``bad`` - a synthetic SandPay finding for the report linter. Everything in it is made up.
"""

from __future__ import annotations

import math
from typing import Optional

from cvss_data import LOOKUP, MAX_COMPOSED, MAX_SEVERITY

# --- metric tables ----------------------------------------------------------------------------------------------

V31_ORDER = ("AV", "AC", "PR", "UI", "S", "C", "I", "A")
V31_VALUES = {"AV": "NALP", "AC": "LH", "PR": "NLH", "UI": "NR", "S": "UC", "C": "HLN", "I": "HLN", "A": "HLN"}

V4_ORDER = ("AV", "AC", "AT", "PR", "UI", "VC", "VI", "VA", "SC", "SI", "SA")
V4_VALUES = {"AV": "NALP", "AC": "LH", "AT": "NP", "PR": "NLH", "UI": "NPA",
             "VC": "HLN", "VI": "HLN", "VA": "HLN", "SC": "HLN", "SI": "HLN", "SA": "HLN"}
V4_THREAT_VALUES = "XAPU"  # Exploit Maturity (E): Not Defined, Attacked, Proof-of-Concept, Unreported

# --- CVSS v4.0: the interpolation step (port of FIRST's cvss_score.js, base + E) --------------------------------

_AV = {"N": 0.0, "A": 0.1, "L": 0.2, "P": 0.3}
_PR = {"N": 0.0, "L": 0.1, "H": 0.2}
_UI = {"N": 0.0, "P": 0.1, "A": 0.2}
_AC = {"L": 0.0, "H": 0.1}
_AT = {"N": 0.0, "P": 0.1}
_VCIA = {"H": 0.0, "L": 0.1, "N": 0.2}
_SC = {"H": 0.1, "L": 0.2, "N": 0.3}
_SIA = {"S": 0.0, "H": 0.1, "L": 0.2, "N": 0.3}


def _parse_composed(text: str) -> dict[str, str]:
    """``"AV:N/PR:N/UI:N/"`` -> ``{"AV": "N", "PR": "N", "UI": "N"}``."""
    return dict(part.split(":") for part in text.strip("/").split("/"))


def interpolate(metrics: dict[str, str], macro: str) -> float:
    """Score a CVSS v4.0 base vector (plus optional E) given its macro vector (six digits, EQ1..EQ6)."""
    if all(metrics[k] == "N" for k in ("VC", "VI", "VA", "SC", "SI", "SA")):
        return 0.0  # no impact on any system: the calculator's shortcut
    eq = [int(c) for c in macro]
    value = LOOKUP[macro]

    def score_of(digits: list[int]) -> Optional[float]:
        return LOOKUP.get("".join(str(d) for d in digits))

    e1, e2, e3, e4, e5, e6 = eq
    lower1 = score_of([e1 + 1, e2, e3, e4, e5, e6])
    lower2 = score_of([e1, e2 + 1, e3, e4, e5, e6])
    if e3 == 1 and e6 == 1:
        lower36 = score_of([e1, e2, e3 + 1, e4, e5, e6])
    elif e3 == 0 and e6 == 1:
        lower36 = score_of([e1, e2, e3 + 1, e4, e5, e6])
    elif e3 == 1 and e6 == 0:
        lower36 = score_of([e1, e2, e3, e4, e5, e6 + 1])
    elif e3 == 0 and e6 == 0:
        left = score_of([e1, e2, e3, e4, e5, e6 + 1])
        right = score_of([e1, e2, e3 + 1, e4, e5, e6])
        present = [s for s in (left, right) if s is not None]
        lower36 = max(present) if present else None
    else:
        lower36 = score_of([e1, e2, e3 + 1, e4, e5, e6 + 1])
    lower4 = score_of([e1, e2, e3, e4 + 1, e5, e6])
    lower5 = score_of([e1, e2, e3, e4, e5 + 1, e6])

    # the highest severity vectors of this macro vector, composed from each EQ's maxima
    candidates = []
    for m1 in MAX_COMPOSED["eq1"][e1]:
        for m2 in MAX_COMPOSED["eq2"][e2]:
            for m36 in MAX_COMPOSED["eq3"][e3][str(e6)]:
                for m4 in MAX_COMPOSED["eq4"][e4]:
                    for m5 in MAX_COMPOSED["eq5"][e5]:
                        candidates.append(_parse_composed(m1 + m2 + m36 + m4 + m5))

    dist: dict[str, float] = {}
    for top in candidates:
        dist = {
            "AV": _AV[metrics["AV"]] - _AV[top["AV"]], "PR": _PR[metrics["PR"]] - _PR[top["PR"]],
            "UI": _UI[metrics["UI"]] - _UI[top["UI"]], "AC": _AC[metrics["AC"]] - _AC[top["AC"]],
            "AT": _AT[metrics["AT"]] - _AT[top["AT"]],
            "VC": _VCIA[metrics["VC"]] - _VCIA[top["VC"]], "VI": _VCIA[metrics["VI"]] - _VCIA[top["VI"]],
            "VA": _VCIA[metrics["VA"]] - _VCIA[top["VA"]],
            "SC": _SC[metrics["SC"]] - _SC[top["SC"]], "SI": _SIA[metrics["SI"]] - _SIA[top["SI"]],
            "SA": _SIA[metrics["SA"]] - _SIA[top["SA"]],
            # Confidentiality/Integrity/Availability Requirement default to High (0.0 against High maxima),
            # so they never add distance in a base or base+threat score.
            "CR": 0.0 - _requirement(top["CR"]), "IR": 0.0 - _requirement(top["IR"]),
            "AR": 0.0 - _requirement(top["AR"]),
        }
        if all(v >= 0 for v in dist.values()):
            break  # the first highest vector that is at least as severe as this one

    d1 = dist["AV"] + dist["PR"] + dist["UI"]
    d2 = dist["AC"] + dist["AT"]
    d36 = dist["VC"] + dist["VI"] + dist["VA"] + dist["CR"] + dist["IR"] + dist["AR"]
    d4 = dist["SC"] + dist["SI"] + dist["SA"]

    step = 0.1
    depth1 = MAX_SEVERITY["eq1"][e1] * step
    depth2 = MAX_SEVERITY["eq2"][e2] * step
    depth36 = MAX_SEVERITY["eq3eq6"][e3][e6] * step
    depth4 = MAX_SEVERITY["eq4"][e4] * step

    parts = []
    for lower, distance, depth in ((lower1, d1, depth1), (lower2, d2, depth2), (lower36, d36, depth36),
                                   (lower4, d4, depth4), (lower5, 0.0, None)):
        if lower is None:
            continue  # no lower macro vector in this direction
        available = value - lower
        parts.append(available * (distance / depth if depth else 0.0))
    mean = sum(parts) / len(parts) if parts else 0.0
    value = min(10.0, max(0.0, value - mean))
    return math.floor(value * 10 + 0.5) / 10  # JavaScript's Math.round


def _requirement(level: str) -> float:
    return {"H": 0.0, "M": 0.1, "L": 0.2}[level]


# --- vectors printed on FIRST's examples page ---------------------------------------------------------------

# One entry of the page is left out: its Log4j "Variation 1" block prints Base 8.2 for
# CVSS:4.0/AV:N/AC:H/AT:P/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N, but the same page prints 8.2 for that vector WITH
# E:P (regreSSHion) and the calculator tables give 9.2 without E. That looks like a page inconsistency (not confirmed).
V31_PUBLISHED = {
    "CVSS:3.1/AV:L/AC:H/PR:L/UI:N/S:U/C:H/I:H/A:H": 7.0,
    "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H": 8.1,
    "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N": 7.5,
    "CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:L/I:N/A:N": 3.3,
    "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N": 6.1,
    "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:L/I:L/A:N": 7.2,
    "CVSS:3.1/AV:L/AC:L/PR:H/UI:N/S:C/C:H/I:N/A:N": 6.0,
    "CVSS:3.1/AV:L/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H": 9.3,
    "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N": 7.5,
    "CVSS:3.1/AV:P/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H": 6.8,
    "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H": 10.0,
    "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H": 9.8,
    "CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:C/C:H/I:N/A:H": 9.3,
    "CVSS:3.1/AV:L/AC:L/PR:H/UI:N/S:C/C:H/I:H/A:H": 8.2,
    "CVSS:3.1/AV:L/AC:L/PR:H/UI:N/S:U/C:N/I:H/A:H": 6.0,
    "CVSS:3.1/AV:P/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H": 7.6,
    "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N": 6.5,
    "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:N/A:N": 5.9,
    "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H": 7.5,
    "CVSS:3.1/AV:N/AC:L/PR:L/UI:R/S:C/C:L/I:L/A:N": 5.4,
    "CVSS:3.1/AV:N/AC:L/PR:L/UI:R/S:C/C:H/I:H/A:H": 9.0,
    "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:N/I:L/A:N": 4.3,
    "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H": 8.8,
    "CVSS:3.1/AV:L/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:N": 6.0,
    "CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H": 7.8,
    "CVSS:3.1/AV:P/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H": 6.4,
    "CVSS:3.1/AV:N/AC:L/PR:H/UI:N/S:U/C:H/I:N/A:N": 4.9,
    "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:N/I:L/A:N": 5.8,
    "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:L": 7.3,
    "CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N": 8.1,
    "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:L/A:H": 9.9,
    "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H": 7.8,
    "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H": 9.9,
}

V4_PUBLISHED = {
    "CVSS:4.0/AV:L/AC:L/AT:P/PR:L/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N": 7.3,
    "CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:P/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N": 7.7,
    "CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:P/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N/E:U": 5.2,
    "CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:H/VI:L/VA:L/SC:N/SI:N/SA:N": 8.3,
    "CVSS:4.0/AV:L/AC:L/AT:N/PR:N/UI:A/VC:L/VI:N/VA:N/SC:N/SI:N/SA:N": 4.6,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:A/VC:N/VI:N/VA:N/SC:L/SI:L/SA:N": 5.1,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:L/SI:L/SA:N": 6.9,
    "CVSS:4.0/AV:L/AC:L/AT:N/PR:H/UI:N/VC:N/VI:N/VA:N/SC:H/SI:N/SA:N": 5.9,
    "CVSS:4.0/AV:L/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H": 9.4,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:H/VA:N/SC:H/SI:H/SA:H": 9.3,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:H/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N/E:A": 8.6,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N/E:A": 8.7,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N/E:A": 9.3,
    "CVSS:4.0/AV:A/AC:L/AT:N/PR:N/UI:N/VC:N/VI:L/VA:N/SC:H/SI:N/SA:H": 6.4,
    "CVSS:4.0/AV:P/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N": 7.0,
    "CVSS:4.0/AV:N/AC:H/AT:P/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N/E:P": 8.2,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N": 7.1,
    "CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N": 8.2,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:L": 8.7,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:L/E:U": 6.6,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:A/VC:L/VI:L/VA:N/SC:L/SI:L/SA:N": 5.1,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:P/VC:N/VI:N/VA:N/SC:L/SI:L/SA:N": 5.1,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:A/VC:H/VI:H/VA:H/SC:L/SI:L/SA:N": 8.5,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:A/VC:N/VI:L/VA:N/SC:N/SI:N/SA:N": 5.1,
    "CVSS:4.0/AV:N/AC:L/AT:P/PR:L/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N": 7.7,
    "CVSS:4.0/AV:L/AC:L/AT:N/PR:H/UI:N/VC:H/VI:H/VA:N/SC:N/SI:N/SA:N": 8.3,
    "CVSS:4.0/AV:L/AC:L/AT:N/PR:H/UI:N/VC:H/VI:H/VA:N/SC:N/SI:N/SA:N/E:U": 5.6,
    "CVSS:4.0/AV:L/AC:L/AT:N/PR:N/UI:P/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N": 8.5,
    "CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N/E:A": 9.2,
    "CVSS:4.0/AV:P/AC:L/AT:P/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N": 5.4,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N": 8.7,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:H/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N": 6.9,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N": 9.3,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:L/SA:N": 6.9,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:L/VA:N/SC:L/SI:N/SA:H": 7.8,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:L/VA:N/SC:L/SI:L/SA:L": 6.9,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:N/VI:N/VA:N/SC:H/SI:L/SA:H": 6.4,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H": 10.0,
    "CVSS:4.0/AV:L/AC:L/AT:N/PR:L/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N": 8.5,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N": 7.1,
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H": 9.4,
}


# --- a synthetic finding for the report linter -----------------------------------------------------------------

GOOD_FINDING = {
    "title": "Any signed-in merchant can read another merchant's payments (IDOR on GET /api/payments/{id})",
    "affected": {"component": "SandPay Merchant Portal (practice build)", "endpoint": "GET /api/payments/{id}"},
    "cwe": "CWE-639",
    "cvss": {"version": "4.0", "vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N",
             "score": 7.1, "rating": "High"},
    "summary": "The payment detail endpoint checks that the caller is signed in but not that the payment belongs to "
               "the caller's merchant, so any merchant can read every other merchant's payments by changing the id.",
    "steps": [
        "Sign in as alice@shop-a.example (merchant m_100) and keep the token.",
        "Request GET /api/payments/pay_2001 - a payment of merchant m_200 - with Alice's token.",
        "Observe 200 with the payment of m_200 instead of 403 or 404.",
    ],
    "evidence": [
        {"request": "GET /api/payments/pay_2001  Authorization: Bearer [REDACTED]",
         "response": "200 {\"id\": \"pay_2001\", \"merchant_id\": \"m_200\", \"amount_minor\": 4999, "
                     "\"currency\": \"EUR\", \"status\": \"captured\", \"card_last4\": \"1881\"}"},
    ],
    "impact": "A merchant can read the payment records of every other merchant, including amounts, statuses and the "
              "last four card digits, which breaks tenant isolation.",
    "remediation": "Authorise the object, not only the caller: return 404 unless payment.merchant_id equals the "
                   "caller's merchant, and add a two-account regression test.",
    "references": ["OWASP API Security Top 10:2023 - API1 Broken Object Level Authorization"],
    "found_on": "2026-11-21",
}


def stub_score_of(vector: str) -> float:
    """What the linter test passes as ``score_of``: a lookup of the vectors printed by FIRST (and this lesson's)."""
    table = {**V31_PUBLISHED, **V4_PUBLISHED, GOOD_FINDING["cvss"]["vector"]: GOOD_FINDING["cvss"]["score"]}
    if vector not in table:
        raise ValueError(f"not a vector this stub knows: {vector!r}")
    return table[vector]
