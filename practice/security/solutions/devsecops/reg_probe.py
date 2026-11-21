"""SOLUTION - Turn three confirmed findings into probes, and prove each probe with the red/green pair.

A regression test for a security finding is a probe plus a rule about WHEN it must report the flaw:

- on the build that still has the flaw it must report it (red) - otherwise it is blind;
- on the build where only that flaw is fixed it must stay quiet (green) - otherwise it is a false positive;
- it must run a POSITIVE CONTROL first (a request that has to work), and raise ``RuntimeError`` when the control
  fails, so a broken login or a wrong URL is never mistaken for "not vulnerable".

Probes return a bool and never return or print what they found: the path-traversal probe proves that the
secret file was served by looking for its first key name, and keeps the contents to itself.
"""

from __future__ import annotations

import urllib.parse
from typing import Callable

import requests
from reg_fixture import PairResult
from sandpay_vuln import make_app, serve

ALICE = ("alice@shop-a.example", "alice-pass-1")  # merchant m_100
EVIL = "https://evil.example/"  # never contacted: the probe does not follow redirects


def _login(base_url: str, email: str, password: str) -> str:
    resp = requests.post(base_url + "/api/login", json={"email": email, "password": password}, timeout=5)
    if resp.status_code != 200:
        raise RuntimeError(f"control failed: login answered {resp.status_code}")
    return resp.json()["token"]


def probe_idor(base_url: str) -> bool:
    """True when Alice (merchant m_100) can read Bob's payment ``pay_2001`` (merchant m_200)."""
    token = _login(base_url, *ALICE)
    headers = {"Authorization": f"Bearer {token}"}
    own = requests.get(base_url + "/api/payments/pay_1001", headers=headers, timeout=5)
    if own.status_code != 200 or own.json().get("merchant_id") != "m_100":
        raise RuntimeError("control failed: Alice cannot read her own payment")
    other = requests.get(base_url + "/api/payments/pay_2001", headers=headers, timeout=5)
    return other.status_code == 200 and other.json().get("merchant_id") == "m_200"


def probe_open_redirect(base_url: str) -> bool:
    """True when ``/login?next=`` redirects to another site. Redirects are never followed."""
    ok = requests.get(base_url + "/login", params={"next": "/settings"}, allow_redirects=False, timeout=5)
    if ok.status_code != 302 or ok.headers.get("Location") != "/settings":
        raise RuntimeError("control failed: a local next= is not redirected as expected")
    bad = requests.get(base_url + "/login", params={"next": EVIL}, allow_redirects=False, timeout=5)
    location = bad.headers.get("Location", "")
    return bad.status_code == 302 and urllib.parse.urlsplit(location).netloc == "evil.example"


def probe_path_traversal(base_url: str) -> bool:
    """True when ``/files?name=../internal/settlement-keys.txt`` serves the internal file."""
    ok = requests.get(base_url + "/files", params={"name": "terms.txt"}, timeout=5)
    if ok.status_code != 200 or "merchant terms" not in ok.text:
        raise RuntimeError("control failed: a public file is not served as expected")
    bad = requests.get(base_url + "/files", params={"name": "../internal/settlement-keys.txt"}, timeout=5)
    return bad.status_code == 200 and "SETTLEMENT_SIGNING_KEY=" in bad.text  # the value is never kept


PROBES: dict[str, Callable[[str], bool]] = {
    "idor": probe_idor,
    "open-redirect": probe_open_redirect,
    "path-traversal": probe_path_traversal,
}


def prove_pair(flaw: str, probe: Callable[[str], bool] | None = None) -> PairResult:
    """Run ``probe`` (default: ``PROBES[flaw]``) on the vulnerable portal and on the portal with only ``flaw`` fixed.

    Verdict: ``"red-green"`` (found, then not found), ``"noisy"`` (it reports the flaw on the fixed build, whatever it
    said before), ``"blind"`` (it never reports the flaw). Raise ``ValueError`` for a flaw with no probe.
    """
    if probe is None:
        if flaw not in PROBES:
            raise ValueError(f"no probe for flaw {flaw!r}")
        probe = PROBES[flaw]
    with serve(make_app()) as base:
        found_vulnerable = bool(probe(base))
    with serve(make_app({flaw})) as base:
        found_fixed = bool(probe(base))
    if found_fixed:
        verdict = "noisy"
    elif not found_vulnerable:
        verdict = "blind"
    else:
        verdict = "red-green"
    return PairResult(flaw, found_vulnerable, found_fixed, verdict)
