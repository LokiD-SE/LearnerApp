"""Turn three confirmed findings into probes, and prove each probe with the red/green pair (regression lesson).

Exercise - fill in the TODOs; ``tests/devsecops/test_reg_probe.py`` checks your work.

A regression test for a security finding is a probe plus a rule about WHEN it must report the flaw:

- on the build that still has the flaw it must report it (red) - otherwise it is blind;
- on the build where only that flaw is fixed it must stay quiet (green) - otherwise it is a false positive;
- it runs a POSITIVE CONTROL first (a request that has to work) and raises ``RuntimeError`` when the control fails, so
  a broken login or a wrong URL is never mistaken for "not vulnerable".

Probes return a bool and never return or print what they found.

- ``probe_idor``: log in as Alice (``ALICE``, merchant m_100). Control: ``GET /api/payments/pay_1001`` with her bearer
  token is a 200 whose ``merchant_id`` is ``m_100``. Then ``GET /api/payments/pay_2001`` (Bob's, merchant m_200): True
  when that is a 200 with ``merchant_id`` ``m_200``. A failed login is a ``RuntimeError`` too.
- ``probe_open_redirect``: control ``GET /login?next=/settings`` (no redirects followed) is a 302 with ``Location`` equal
  to ``/settings``. Then ``next=EVIL``: True when it is a 302 whose ``Location`` host is ``evil.example``.
- ``probe_path_traversal``: control ``GET /files?name=terms.txt`` is a 200 containing ``merchant terms``. Then
  ``name=../internal/settlement-keys.txt``: True when it is a 200 whose body contains ``SETTLEMENT_SIGNING_KEY=``.
- ``prove_pair(flaw, probe=None)``: run the probe on ``serve(make_app())`` and on ``serve(make_app({flaw}))``. Verdict
  ``"noisy"`` if it reports the flaw on the fixed build, else ``"blind"`` if it never reported it, else ``"red-green"``.
  A flaw with no probe (and no ``probe`` given) is a ``ValueError``.
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
    """The bearer token for the account. Raise ``RuntimeError`` when the login is not a 200."""
    resp = requests.post(base_url + "/api/login", json={"email": email, "password": password}, timeout=5)
    if resp.status_code != 200:
        raise RuntimeError(f"control failed: login answered {resp.status_code}")
    return resp.json()["token"]


def probe_idor(base_url: str) -> bool:
    """True when Alice can read Bob's payment.

    TODO: log in, run the control, then request ``pay_2001`` as described in the module docstring.
    """
    raise NotImplementedError("probe_idor")


def probe_open_redirect(base_url: str) -> bool:
    """True when ``/login?next=`` redirects to another site.

    TODO: control first, then the attack; use ``allow_redirects=False`` and ``urllib.parse.urlsplit``.
    """
    raise NotImplementedError("probe_open_redirect")


def probe_path_traversal(base_url: str) -> bool:
    """True when the internal settlement file is served.

    TODO: control first, then the traversal name; look for the key NAME, never keep the value.
    """
    raise NotImplementedError("probe_path_traversal")


PROBES: dict[str, Callable[[str], bool]] = {
    "idor": probe_idor,
    "open-redirect": probe_open_redirect,
    "path-traversal": probe_path_traversal,
}


def prove_pair(flaw: str, probe: Callable[[str], bool] | None = None) -> PairResult:
    """Run the probe on the vulnerable portal and on the portal with only ``flaw`` fixed; return the verdict.

    TODO: pick the probe, serve the two portals, build a ``PairResult`` (see the module docstring for the verdicts).
    """
    raise NotImplementedError("prove_pair")
