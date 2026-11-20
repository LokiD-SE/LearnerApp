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
    """TODO: Sign in with POST /api/login (JSON body ``email`` and ``password``) and return the ``token`` field.
    RuntimeError when the sign-in is not a 200 - a probe that cannot set up its precondition must say so."""
    raise NotImplementedError("get_token")


def forge_unsigned(claims: dict, alg: str = "none") -> str:
    """TODO: An unsecured JWT: ``b64url_json({"alg": alg, "typ": "JWT"})`` + "." + ``b64url_json(claims)`` + "." and
    NOTHING after the last dot - the signature is the empty string, which is why such a token ends with a dot."""
    raise NotImplementedError("forge_unsigned")


def forge_tampered(token: str, changes: dict) -> str:
    """TODO: The same token with ``changes`` merged into its payload. Keep the header and the OLD signature exactly
    as they were; re-encode only the payload (base64url, no padding)."""
    raise NotImplementedError("forge_tampered")


def _call(base_url: str, token: str | None, timeout: float, path: str = PROTECTED_PATH) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.get(f"{base_url}{path}", headers=headers, timeout=timeout)


def probe_alg_none(base_url: str, valid_token: str, victim_email: str, timeout: float = 5,
                   path: str = PROTECTED_PATH) -> AlgNoneResult:
    """TODO, in this order:
    1. Baseline: call ``path`` with no token. Anything other than 401 or 403 means the endpoint does not
       authenticate - raise RuntimeError, because the probe cannot conclude anything.
    2. Call it with ``valid_token``: it must be 200, else RuntimeError (the precondition failed).
    3. Signature check: send ``forge_tampered(valid_token, {"sub": victim_email})``; ``tampered_rejected`` is True
       when the answer is 401 or 403.
    4. For each spelling in SPELLINGS send ``forge_unsigned({"sub": victim_email, "exp": now + 300}, alg=spelling)``.
       A spelling is accepted when the answer is 200 AND the JSON ``email`` is the victim's; record the accepted
       spellings and the ``role`` the API reported.
    5. ``vulnerable`` is True when any spelling was accepted or the signature is not checked."""
    raise NotImplementedError("probe_alg_none")
