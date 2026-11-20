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
    if set(policy.algorithms) - set(HMAC_ALGS):
        raise ValueError(f"this validator implements only {sorted(HMAC_ALGS)}; never 'none'")
    try:
        header, claims, signature, signing_input = split_token(token)
    except ValueError:
        return Verdict(False, ["malformed"])
    alg = header.get("alg")
    if not isinstance(alg, str) or alg not in policy.algorithms:
        return Verdict(False, ["alg-not-allowed"])
    expected = hmac.new(policy.key, signing_input.encode(), HMAC_ALGS[alg]).digest()
    try:
        given = _b64url_decode(signature)
    except ValueError:
        return Verdict(False, ["bad-signature"])
    if not hmac.compare_digest(expected, given):
        return Verdict(False, ["bad-signature"])

    reasons: list[str] = []
    required = list(policy.require)
    if policy.issuer is not None:
        required.append("iss")
    if policy.audience is not None:
        required.append("aud")
    for name in dict.fromkeys(required):
        if name not in claims:
            reasons.append(f"missing-{name}")
    for name in ("exp", "nbf", "iat"):
        if name in claims and not _number(claims[name]):
            reasons.append(f"bad-claim:{name}")
    if _number(claims.get("exp")) and now - policy.leeway_s >= claims["exp"]:
        reasons.append("expired")
    if _number(claims.get("nbf")) and claims["nbf"] - policy.leeway_s > now:
        reasons.append("not-yet-valid")
    if policy.issuer is not None and "iss" in claims and claims["iss"] != policy.issuer:
        reasons.append("issuer-mismatch")
    if policy.audience is not None and "aud" in claims:
        aud = claims["aud"]
        values = aud if isinstance(aud, list) else [aud]
        if policy.audience not in values:
            reasons.append("audience-mismatch")
    if (policy.max_lifetime_s is not None and _number(claims.get("exp")) and _number(claims.get("iat"))
            and claims["exp"] - claims["iat"] > policy.max_lifetime_s):
        reasons.append("lifetime-too-long")
    return Verdict(not reasons, reasons)
