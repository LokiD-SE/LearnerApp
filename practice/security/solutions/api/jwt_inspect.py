"""Reading a JWT the way a tester does - WSTG-SESS-10 "Analyse the Contents".

A JWT is three base64url parts joined by dots: header, payload, signature (RFC 7519 section 3; this is the signed
form, the JWS compact serialisation - an encrypted JWT has five parts and is not covered here). Base64url is an
ENCODING, not encryption: anyone who holds the token can read the header and the claims. Decoding therefore says
nothing about whether the token is genuine - this module never verifies a signature. It answers two other
questions: what does the token reveal, and does what it reveals look wrong?

``describe_token`` returns finding codes (sorted, no duplicates):

- ``alg-none``: the header's ``alg`` is "none" in any spelling (an unsecured JWT, RFC 7519 section 6);
- ``missing-exp`` / ``expired`` / ``long-lived``: lifetime problems. The lifetime is ``exp - iat`` when ``iat`` is
  present, else ``exp - now``; it is long-lived above ``max_lifetime_s``;
- ``untrusted-header:<name>`` for ``jwk``, ``jku``, ``x5u`` and ``kid``: header parameters that name key material the
  verifier must not follow blindly (RFC 8725 section 3.10);
- ``sensitive-claim:<path>`` for a claim whose name contains one of SENSITIVE_WORDS as a whole word
  (``password_hash`` and ``card_number`` do; ``company`` does not), searched inside nested objects too.

Everything here is data analysis on text you already hold. Test only systems you own or have written permission
to test.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass

SENSITIVE_WORDS = {"password", "passwd", "pwd", "secret", "hash", "card", "pan", "ssn"}
UNTRUSTED_HEADERS = ("jwk", "jku", "x5u", "kid")
_B64URL = re.compile(r"^[A-Za-z0-9_-]*$")


@dataclass
class DecodedJwt:
    header: dict
    payload: dict
    signature: str  # the third part, still base64url text ("" for an unsecured JWT)
    signing_input: str  # "<header>.<payload>" exactly as sent - what a signature covers


def b64url_decode(text: str) -> bytes:
    """Base64url decode with the padding JWTs leave out (RFC 7515 appendix C). ValueError on other characters."""
    if not _B64URL.match(text):
        raise ValueError("not base64url")
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except binascii.Error as exc:
        raise ValueError("not base64url") from exc


def _json_object(part: str, what: str) -> dict:
    try:
        value = json.loads(b64url_decode(part))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"{what} is not base64url-encoded JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{what} is not a JSON object")
    return value


def decode_token(token: str) -> DecodedJwt:
    """Splits a compact JWT into header, payload and signature WITHOUT verifying anything."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError(f"a compact JWT has 3 dot-separated parts, this has {len(parts)}")
    return DecodedJwt(_json_object(parts[0], "header"), _json_object(parts[1], "payload"), parts[2],
                      f"{parts[0]}.{parts[1]}")


def _sensitive_paths(obj: dict, prefix: str = "") -> list[str]:
    found = []
    for name, value in obj.items():
        path = f"{prefix}{name}"
        words = set(re.split(r"[^a-z0-9]+", str(name).lower()))
        if words & SENSITIVE_WORDS:
            found.append(path)
        if isinstance(value, dict):
            found.extend(_sensitive_paths(value, f"{path}."))
    return found


def describe_token(token: str, now: float, max_lifetime_s: int = 3600) -> list[str]:
    """Finding codes for ``token`` as of time ``now`` (see the module docstring). ValueError if it cannot be decoded."""
    jwt = decode_token(token)
    findings: set[str] = set()
    if str(jwt.header.get("alg", "")).lower() == "none":
        findings.add("alg-none")
    exp, iat = jwt.payload.get("exp"), jwt.payload.get("iat")
    if not isinstance(exp, (int, float)) or isinstance(exp, bool):
        findings.add("missing-exp")
    else:
        if exp <= now:
            findings.add("expired")
        start = iat if isinstance(iat, (int, float)) and not isinstance(iat, bool) else now
        if exp - start > max_lifetime_s:
            findings.add("long-lived")
    for name in UNTRUSTED_HEADERS:
        if name in jwt.header:
            findings.add(f"untrusted-header:{name}")
    findings.update(f"sensitive-claim:{path}" for path in _sensitive_paths(jwt.payload))
    return sorted(findings)
