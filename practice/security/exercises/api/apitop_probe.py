"""EXERCISE - One probe per API risk the practice portal can show, each with a control and no false positive.

Four checks are written for you (``check_bola``, ``check_property_read``, ``check_error_detail``,
``check_security_headers``) - read them first. Write the other four and ``probe_api``, which runs all eight.

``probe_api`` runs eight small checks against a SandPay portal and returns a ``Finding`` for every one that
shows its flaw. Every check follows the house pattern: it must FIND the flaw on ``make_app()`` and stay QUIET
on the same portal with that flaw fixed. Each check uses a harmless request - it reads, sends a value that
changes nothing, or asks the server to fetch its own ``/health``.

| risk (OWASP API Top 10:2023)                | flaw id          | the check                                            |
| ------------------------------------------- | ---------------- | ---------------------------------------------------- |
| API1 Broken Object Level Authorization      | ``idor``         | A reads one of B's payments                          |
| API2 Broken Authentication                  | ``jwt-none``     | an unsigned (``alg: none``) token is accepted        |
| API3 Broken Object Property Level Auth.     | ``mass-assignment`` | PATCH sends ``role`` (same value) and is accepted |
| API3 Broken Object Property Level Auth.     | ``data-exposure``| the merchant object returns its secret and full IBAN |
| API4 Unrestricted Resource Consumption      | ``no-rate-limit``| eight wrong sign-ins and no 429                      |
| API7 Server Side Request Forgery            | ``ssrf``         | the webhook test fetches a loopback URL              |
| API8 Security Misconfiguration              | ``verbose-errors``| an error returns a Python traceback                 |
| API8 Security Misconfiguration              | ``missing-headers``| no ``X-Content-Type-Options``                      |
"""

from __future__ import annotations

from dataclasses import dataclass

import requests
from sandpay_vuln import LOGIN_LIMIT, make_jwt

SENSITIVE_MERCHANT_KEYS = {"api_secret", "payout_iban"}


@dataclass(frozen=True)
class Finding:
    risk: str      # "API1:2023"
    flaw: str      # the practice portal's flaw id
    evidence: str  # one line that proves it (status, a key, a header) - never a secret value


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _get(base_url: str, path: str, token: str | None = None) -> requests.Response:
    return requests.get(base_url + path, headers=_auth(token) if token else {}, allow_redirects=False, timeout=5)


def check_bola(base_url: str, token_a: str, token_b: str) -> Finding | None:
    """API1: can A read a payment that B owns? B's id comes from B's own listing."""
    mine = _get(base_url, "/api/me", token_a).json()["merchant_id"]
    ids_b = [p["id"] for p in _get(base_url, "/api/payments", token_b).json()["data"]]
    if not ids_b:
        raise ValueError("account B owns no payments, so there is nothing to try")
    resp = _get(base_url, f"/api/payments/{ids_b[0]}", token_a)
    if resp.status_code == 200 and resp.json().get("merchant_id") not in (None, mine):
        return Finding("API1:2023", "idor", f"{ids_b[0]} readable by another merchant: {resp.status_code}")
    return None


def check_unsigned_jwt(base_url: str, email: str) -> Finding | None:
    """API2: is a token with ``alg: none`` and no signature accepted?"""
    raise NotImplementedError("TODO: implement check_unsigned_jwt")


def check_login_rate_limit(base_url: str, attempts: int = LOGIN_LIMIT + 3) -> Finding | None:
    """API4: do repeated wrong sign-ins for ONE account ever get a 429? Uses an account that does not exist."""
    raise NotImplementedError("TODO: implement check_login_rate_limit")


def check_property_write(base_url: str, token: str) -> Finding | None:
    """API3 (write): does PATCH /api/profile accept ``role``? Send the role the user already has, so nothing changes."""
    raise NotImplementedError("TODO: implement check_property_write")


def check_property_read(base_url: str, token: str) -> Finding | None:
    """API3 (read): does the caller's own merchant object carry secrets? Report the key names, not the values."""
    merchant = _get(base_url, "/api/me", token).json()["merchant_id"]
    body = _get(base_url, f"/api/merchants/{merchant}", token).json()
    leaked = sorted(SENSITIVE_MERCHANT_KEYS & set(body))
    if leaked:
        return Finding("API3:2023", "data-exposure", f"GET /api/merchants/{merchant} returns {', '.join(leaked)}")
    return None


def check_ssrf(base_url: str, token: str) -> Finding | None:
    """API7: ask the webhook test to fetch the portal's own /health. Loopback only - nothing leaves the machine."""
    raise NotImplementedError("TODO: implement check_ssrf")


def check_error_detail(base_url: str) -> Finding | None:
    """API8: does an unhandled error answer with a stack trace?"""
    resp = _get(base_url, "/boom")
    if resp.status_code == 500 and "Traceback" in resp.text:
        return Finding("API8:2023", "verbose-errors", "GET /boom returned a Python traceback: 500")
    return None


def check_security_headers(base_url: str) -> Finding | None:
    """API8: is the ``X-Content-Type-Options`` header missing from an API response?"""
    resp = _get(base_url, "/health")
    if "X-Content-Type-Options" not in resp.headers:
        return Finding("API8:2023", "missing-headers", f"no X-Content-Type-Options; Server: {resp.headers.get('Server')}")
    return None


def probe_api(base_url: str, token_a: str, token_b: str) -> list[Finding]:
    """Run every check as account A (B only supplies real ids) and return the findings, in risk order.

    Raise ``RuntimeError`` first if A cannot call ``GET /api/me`` - the control. Without it a "no finding" would
    only mean the token does not work.
    """
    raise NotImplementedError("TODO: implement probe_api")