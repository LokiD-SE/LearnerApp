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
    """TODO: Base64url decode ``text``. JWTs leave the ``=`` padding out (RFC 7515 appendix C), so add back as many
    ``=`` as needed to reach a multiple of 4 first. ValueError if ``text`` has characters outside
    ``A-Z a-z 0-9 - _`` (standard base64's ``+`` and ``/`` are not base64url)."""
    raise NotImplementedError("b64url_decode")


def decode_token(token: str) -> DecodedJwt:
    """TODO: Split a compact JWT into header, payload and signature WITHOUT verifying anything.
    ValueError unless the token has exactly 3 dot-separated parts and the first two are base64url-encoded JSON
    *objects* (a JSON array or text is not a header or a claims set). ``signing_input`` is the first two parts
    joined by a dot, exactly as sent."""
    raise NotImplementedError("decode_token")


def describe_token(token: str, now: float, max_lifetime_s: int = 3600) -> list[str]:
    """TODO: Finding codes for ``token`` as of time ``now`` - see the module docstring for the list and the rules.
    Return them sorted without duplicates; raise ValueError if the token cannot be decoded. Hints: ``exp`` counts as
    expired when ``exp <= now``; a boolean is not a number; search nested objects for sensitive claim names and
    report the dotted path (``data.password``); match sensitive words as whole words, not substrings."""
    raise NotImplementedError("describe_token")
