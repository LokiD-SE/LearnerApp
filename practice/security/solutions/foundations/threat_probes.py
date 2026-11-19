"""Threat modelling, part 2: turn threats from the register into executable checks.

Each function takes the portal's base URL (the deliberately vulnerable SandPay portal, support/sandpay_vuln.py,
on loopback only) and returns True when the threat is REALISED - the attack worked - and False when it was
stopped. A good check is True against ``make_app()`` and False once the matching flaw is fixed.

The one exception is ``lockout_denial``: it tests a threat the FIX creates. A per-account login limit stops
password guessing (spoofing) but lets an attacker lock a merchant out (denial of service) - so this check is
False against the vulnerable portal and True against the fixed one. A mitigation is a design change, and a
design change needs its own threat review.
"""

from __future__ import annotations

import base64
import json

import requests

TIMEOUT = 5


def _login(base_url: str, email: str, password: str) -> requests.Response:
    return requests.post(f"{base_url}/api/login", json={"email": email, "password": password}, timeout=TIMEOUT)


def _token(base_url: str, email: str, password: str) -> str:
    r = _login(base_url, email, password)
    r.raise_for_status()
    return r.json()["token"]


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unsigned_token(claims: dict) -> str:
    """A JWT with ``"alg": "none"`` and an empty signature (RFC 7519 section 6, "Unsecured JWTs")."""
    header = _b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps(claims).encode())
    return f"{header}.{payload}."


def spoofing_unsigned_token(base_url: str, victim_email: str = "ops@sandpay.example") -> bool:
    """S - Spoofing (violates authentication): does the portal accept an unsigned token claiming to be the
    victim? Realised when ``GET /api/me`` answers 200 with the victim's email."""
    r = requests.get(f"{base_url}/api/me", headers={"Authorization": f"Bearer {unsigned_token({'sub': victim_email})}"},
                     timeout=TIMEOUT)
    return r.status_code == 200 and r.json().get("email") == victim_email


def elevation_via_profile_update(base_url: str, email: str, password: str) -> bool:
    """E - Elevation of privilege (violates authorization): can a merchant make themselves an admin by
    sending ``role`` in a profile update? Realised when ``GET /api/me`` then reports ``role: admin``."""
    auth = {"Authorization": f"Bearer {_token(base_url, email, password)}"}
    requests.patch(f"{base_url}/api/profile", json={"display_name": "Probe", "role": "admin"}, headers=auth,
                   timeout=TIMEOUT)
    me = requests.get(f"{base_url}/api/me", headers=auth, timeout=TIMEOUT)
    return me.status_code == 200 and me.json().get("role") == "admin"


def disclosure_cross_merchant(base_url: str, email: str, password: str, other_payment_id: str) -> bool:
    """I - Information disclosure (violates confidentiality): can a merchant read a payment that belongs to
    another merchant? Realised when the payment comes back (200) with a merchant id that is not the caller's."""
    login = _login(base_url, email, password)
    login.raise_for_status()
    mine = login.json()["merchant_id"]
    r = requests.get(f"{base_url}/api/payments/{other_payment_id}",
                     headers={"Authorization": f"Bearer {login.json()['token']}"}, timeout=TIMEOUT)
    return r.status_code == 200 and r.json().get("merchant_id") not in (None, mine)


def spoofing_by_guessing(base_url: str, email: str, guesses: int = 8) -> bool:
    """S - Spoofing by password guessing: can an attacker keep guessing one account's password? Realised
    when ``guesses`` wrong passwords in a row are all evaluated (401) - none are throttled (429)."""
    statuses = [_login(base_url, email, f"wrong-guess-{i}").status_code for i in range(guesses)]
    return 429 not in statuses


def lockout_denial(base_url: str, victim_email: str, victim_password: str, attempts: int = 6) -> bool:
    """D - Denial of service created by a mitigation: after an attacker's failed attempts against the
    victim's account, is the victim's own CORRECT password refused? Realised when it is (any non-200)."""
    for i in range(attempts):
        _login(base_url, victim_email, f"attacker-{i}")
    return _login(base_url, victim_email, victim_password).status_code != 200
