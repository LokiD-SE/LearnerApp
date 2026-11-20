"""A JWT validator that follows RFC 7519 section 7.2 and RFC 8725 - the check the portal's fixed verifier should
make, written as a policy a tester can run against any token.

The order matters:

1. ``malformed``: not three parts, or header/payload not JSON objects - reject.
2. ``alg-not-allowed``: the header's ``alg`` must be in the application's allow-list, compared exactly
   (RFC 8725 section 3.1: the library "MUST NOT use any other algorithms"; RFC 7515 section 4.1.1: case-sensitive).
   The allow-list never contains ``none`` here.
3. ``bad-signature``: HMAC over ``header.payload`` with the policy's key, compared in constant time.
   Steps 2 and 3 return at once: claims of a token that is not proven genuine are not worth reading.
4. Claims, all reported together: ``expired``, ``not-yet-valid``, ``missing-<name>``, ``issuer-mismatch``,
   ``audience-mismatch``, ``lifetime-too-long``, ``bad-claim:<name>``.

Only the HMAC family (HS256, HS384, HS512) is implemented, to keep the exercise self-contained; a real service uses
a maintained JWT library and says which algorithms it accepts (RFC 8725 section 3.1).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field

HMAC_ALGS = {"HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512}


@dataclass
class Policy:
    key: bytes
    algorithms: tuple[str, ...] = ("HS256",)
    issuer: str | None = None  # when set, ``iss`` is required and must equal it exactly
    audience: str | None = None  # when set, ``aud`` is required and must contain it
    leeway_s: int = 60  # clock-skew allowance for exp and nbf (RFC 7519: "usually no more than a few minutes")
    max_lifetime_s: int | None = None  # when set, exp - iat above it is too long (needs both claims)
    require: tuple[str, ...] = ("exp",)


@dataclass
class Verdict:
    ok: bool
    reasons: list[str] = field(default_factory=list)


_B64URL = re.compile(r"^[A-Za-z0-9_-]*$")


def _b64url_decode(text: str) -> bytes:
    if not _B64URL.match(text):
        raise ValueError("not base64url")
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except binascii.Error as exc:
        raise ValueError("not base64url") from exc


def split_token(token: str) -> tuple[dict, dict, str, str]:
    """(header, payload, signature text, signing input) of a compact JWT; ValueError if it is not one."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("a compact JWT has 3 parts")
    decoded = []
    for part in parts[:2]:
        try:
            value = json.loads(_b64url_decode(part))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("not base64url-encoded JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("not a JSON object")
        decoded.append(value)
    return decoded[0], decoded[1], parts[2], f"{parts[0]}.{parts[1]}"


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_token(token: str, policy: Policy, now: float) -> Verdict:
    """TODO: Validate ``token`` against ``policy`` as of ``now``, in the order of the module docstring.

    - ValueError first if ``policy.algorithms`` contains anything outside HMAC_ALGS (so never ``none``).
    - ``split_token`` (provided) raises ValueError for a malformed token -> ``Verdict(False, ["malformed"])``.
    - ``alg`` must be a string in ``policy.algorithms``, compared exactly -> else ``["alg-not-allowed"]`` at once.
    - Recompute the HMAC over the signing input with ``policy.key`` and compare in constant time
      (``hmac.compare_digest``); a bad or undecodable signature -> ``["bad-signature"]`` at once.
    - Only then the claims, collecting every reason in this order: ``missing-<name>`` for each required claim
      (``policy.require``, plus ``iss`` when an issuer is set and ``aud`` when an audience is set), ``bad-claim:<name>``
      for a non-numeric exp/nbf/iat, ``expired`` (``now - leeway_s >= exp``), ``not-yet-valid``
      (``nbf - leeway_s > now``), ``issuer-mismatch`` (exact equality), ``audience-mismatch`` (``aud`` may be a string
      or a list; the policy audience must be one of the values, compared exactly), ``lifetime-too-long``
      (``exp - iat > max_lifetime_s`` when both are present).
    - ``Verdict.ok`` is True only when there are no reasons."""
    raise NotImplementedError("validate_token")
