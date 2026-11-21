"""Prints every output the lesson vulnerability-reporting-and-cvss shows. Run from practice/security:

    .venv/bin/python support/cvss_demo.py            (uses the reference solutions)

Everything runs against the in-process practice portal on loopback; nothing leaves the machine.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "solutions"), str(ROOT / "support")]

import requests  # noqa: E402
import cvss_fixture as fx  # noqa: E402
from cvss_data import LOOKUP  # noqa: E402
from sandpay_vuln import make_app, serve  # noqa: E402
from specialised import cvss_report, cvss_v31, cvss_v4  # noqa: E402

IDOR_V31 = "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"
IDOR_V4 = "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N"


def heading(text: str) -> None:
    print(f"\n=== {text}")


def published() -> None:
    heading("1. Scores against the vectors FIRST printed on its examples page")
    ok31 = sum(cvss_v31.base_score(v) == s for v, s in fx.V31_PUBLISHED.items())
    ok4 = sum(cvss_v4.score(v) == s for v, s in fx.V4_PUBLISHED.items())
    with_e = sum("/E:" in v for v in fx.V4_PUBLISHED)
    print(f"v3.1: {ok31} of {len(fx.V31_PUBLISHED)} match")
    print(f"v4.0: {ok4} of {len(fx.V4_PUBLISHED)} match ({with_e} of them carry E)")


def roundup() -> None:
    heading("2. Why Roundup needs integer arithmetic")
    for x in (4.02, 4.00, 4.000000000001):
        naive = math.ceil(x * 10) / 10
        print(f"x = {x!r:<22} naive ceil(x*10)/10 = {naive:<4} roundup = {cvss_v31.roundup(x)}")


def v31_steps() -> None:
    heading("3. The v3.1 base score of the IDOR finding, step by step")
    m = cvss_v31.parse_vector(IDOR_V31)
    w = cvss_v31.WEIGHTS
    iss = 1 - (1 - w["CIA"][m["C"]]) * (1 - w["CIA"][m["I"]]) * (1 - w["CIA"][m["A"]])
    impact = 6.42 * iss
    expl = 8.22 * w["AV"][m["AV"]] * w["AC"][m["AC"]] * cvss_v31.PR_UNCHANGED[m["PR"]] * w["UI"][m["UI"]]
    print(f"ISS = {iss:.4f}   Impact = {impact:.4f}   Exploitability = {expl:.4f}")
    print(f"Impact + Exploitability = {impact + expl:.4f}   base score = {cvss_v31.base_score(IDOR_V31)}")


def v4_steps() -> None:
    heading("4. The v4.0 base score of the same finding: macro vector, table row, distance")
    m = cvss_v4.parse_vector(IDOR_V4)
    macro = cvss_v4.macrovector(m)
    print(f"metrics: {m}")
    print(f"macro vector (EQ1..EQ6) = {macro}   table row score = {LOOKUP[macro]}")
    print(f"score after the distance step = {cvss_v4.score(IDOR_V4)}")
    for e in ("X", "A", "P", "U"):
        v = IDOR_V4 + ("" if e == "X" else f"/E:{e}")
        print(f"  E:{e}  macro {cvss_v4.macrovector(cvss_v4.parse_vector(v))}  score {cvss_v4.score(v)}")


def same_finding_two_versions() -> None:
    heading("5. Three portal findings, scored in both versions (my metric choices - see the lesson)")
    rows = [
        ("IDOR on GET /api/payments/{id}", IDOR_V31, IDOR_V4),
        ("Mass assignment: role=admin on PATCH /api/profile",
         "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H",
         "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"),
        ("Reflected XSS on GET /search?q=",
         "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N",
         "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:A/VC:N/VI:N/VA:N/SC:L/SI:L/SA:N"),
        ("Refund race: two refunds win (the logic_ fixture)",
         "CVSS:3.1/AV:N/AC:H/PR:L/UI:N/S:U/C:N/I:H/A:N",
         "CVSS:4.0/AV:N/AC:L/AT:P/PR:L/UI:N/VC:N/VI:H/VA:N/SC:N/SI:N/SA:N"),
    ]
    print(f"{'finding':<52} {'v3.1':<12} v4.0")
    for name, v31, v4 in rows:
        s31, s4 = cvss_v31.base_score(v31), cvss_v4.score(v4)
        print(f"{name:<52} {s31:<4} {cvss_report.qualitative(s31):<7} {s4:<4} {cvss_report.qualitative(s4)}")


def sensitivity() -> None:
    heading("5b. One metric at a time: how far can a single judgement move the IDOR score?")
    rows = [
        ("as scored (VC:H, PR:L)", IDOR_V4),
        ("VC:L - 'some' restricted information", IDOR_V4.replace("VC:H", "VC:L")),
        ("PR:N - if no sign-in were needed", IDOR_V4.replace("PR:L", "PR:N")),
        ("AT:P - if a precondition had to hold", IDOR_V4.replace("AT:N", "AT:P")),
    ]
    for name, vector in rows:
        s4 = cvss_v4.score(vector)
        print(f"  {name:<46} {s4:<4} {cvss_report.qualitative(s4)}")
    s31 = cvss_v31.base_score(IDOR_V31.replace("C:H", "C:L"))
    print(f"  v3.1 with C:L instead of C:H                   {s31:<4} {cvss_report.qualitative(s31)}")


def _token(base: str, email: str, password: str) -> str:
    reply = requests.post(base + "/api/login", json={"email": email, "password": password}, timeout=5)
    reply.raise_for_status()
    return reply.json()["token"]


def collect_evidence(base: str) -> dict | None:
    """Alice (merchant m_100) asks for a payment of Bob's merchant (m_200). Returns evidence only if it is served."""
    token = _token(base, "alice@shop-a.example", "alice-pass-1")
    reply = requests.get(base + "/api/payments/pay_2001", headers={"Authorization": f"Bearer {token}"}, timeout=5)
    if reply.status_code != 200 or reply.json().get("merchant_id") != "m_200":
        return None
    return {"request": "GET /api/payments/pay_2001  Authorization: Bearer [REDACTED]",
            "response": f"{reply.status_code} {json.dumps(reply.json())}"}


def live_evidence() -> None:
    heading("6. Evidence from the running portal - and nothing from the fixed one")
    with serve(make_app()) as base:
        print("vulnerable:", json.dumps(collect_evidence(base), indent=2))
    with serve(make_app({"idor"})) as base:
        print("idor fixed:", collect_evidence(base))
    finding = json.loads(json.dumps(fx.GOOD_FINDING))
    with serve(make_app()) as base:
        finding["evidence"] = [collect_evidence(base)]
    print("lint of the finished finding:", cvss_report.lint_finding(finding, fx.stub_score_of))


def sloppy() -> None:
    heading("7. The linter on a sloppy first draft")
    draft = {
        "title": "IDOR",
        "affected": {"component": "portal"},
        "cwe": "639",
        "cvss": {"version": "4.0", "vector": IDOR_V4, "score": 9.8, "rating": "Critical"},
        "summary": "You can see other people's payments.",
        "steps": ["Change the id."],
        "evidence": [{"request": "GET /api/payments/pay_2001  Authorization: Bearer eyJhbGciOiJub25lIn0.e30.signature1",
                      "response": ""}],
        "impact": "Critical",
        "remediation": "Fix it.",
    }
    print(cvss_report.lint_finding(draft, fx.stub_score_of))


if __name__ == "__main__":
    published()
    roundup()
    v31_steps()
    v4_steps()
    same_finding_two_versions()
    sensitivity()
    live_evidence()
    sloppy()
