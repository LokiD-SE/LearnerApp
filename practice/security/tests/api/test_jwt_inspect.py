"""Checks exercises/api/jwt_inspect.py: hand-built tokens first, then a real token from the portal."""

import base64
import json
import time

import pytest
import requests
from api.jwt_inspect import b64url_decode, decode_token, describe_token
from sandpay_vuln import make_app, make_jwt, serve

pytestmark = pytest.mark.exercise

NOW = 1_800_000_000  # a fixed "now" so the lifetime checks never depend on the clock


def test_decode_splits_the_three_parts_without_verifying():
    token = make_jwt({"sub": "alice@shop-a.example", "exp": NOW + 600})
    jwt = decode_token(token)
    assert jwt.header == {"alg": "HS256", "typ": "JWT"}
    assert jwt.payload == {"sub": "alice@shop-a.example", "exp": NOW + 600}
    assert jwt.signature == token.split(".")[2] and jwt.signature
    assert jwt.signing_input == ".".join(token.split(".")[:2])


def test_decoding_needs_no_key_and_accepts_a_forged_signature():
    # decode is reading, not trusting: a token with a garbage signature still decodes.
    header, payload, _ = make_jwt({"sub": "x"}).split(".")
    assert decode_token(f"{header}.{payload}.AAAA").payload == {"sub": "x"}


def test_base64url_restores_the_padding_jwts_leave_out():
    assert b64url_decode("YQ") == b"a"
    assert b64url_decode("YWI") == b"ab"
    assert b64url_decode("YWJj") == b"abc"
    assert b64url_decode("-_8") == b"\xfb\xff"
    with pytest.raises(ValueError):
        b64url_decode("a+b/")  # standard base64 characters are not base64url


@pytest.mark.parametrize("bad", ["only-one-part", "a.b", "a.b.c.d", "!!!.e30.sig", "e30.bm90LWpzb24.sig", "e30.WzFd.sig"])
def test_decode_rejects_what_is_not_a_compact_jwt(bad):
    # 'e30' is {} ; 'bm90LWpzb24' is the text not-json ; 'WzFd' is [1] (valid JSON, not an object)
    with pytest.raises(ValueError):
        decode_token(bad)


def test_a_sound_short_lived_token_has_no_findings():
    token = make_jwt({"sub": "alice@shop-a.example", "iat": NOW, "exp": NOW + 900})
    assert describe_token(token, now=NOW + 10) == []


@pytest.mark.parametrize("spelling", ["none", "None", "NONE", "nOnE"])
def test_alg_none_in_any_spelling_is_flagged(spelling):
    token = make_jwt({"sub": "ops@sandpay.example", "exp": NOW + 600}, alg="none")
    payload = token.split(".")[1]
    fake = base64.urlsafe_b64encode(json.dumps({"alg": spelling}).encode()).rstrip(b"=").decode()
    assert "alg-none" in describe_token(f"{fake}.{payload}.", now=NOW)


def test_lifetime_findings():
    assert "missing-exp" in describe_token(make_jwt({"sub": "a"}), now=NOW)
    assert "expired" in describe_token(make_jwt({"sub": "a", "exp": NOW - 1}), now=NOW)
    assert "expired" in describe_token(make_jwt({"sub": "a", "exp": NOW}), now=NOW)  # exp is "on or after" (RFC 7519)
    # lifetime comes from exp - iat when iat is present ...
    assert "long-lived" in describe_token(make_jwt({"sub": "a", "iat": NOW, "exp": NOW + 86400}), now=NOW)
    assert "long-lived" not in describe_token(make_jwt({"sub": "a", "iat": NOW, "exp": NOW + 3600}), now=NOW)
    # ... and from exp - now when it is not
    assert "long-lived" in describe_token(make_jwt({"sub": "a", "exp": NOW + 86400}), now=NOW)
    assert "long-lived" not in describe_token(make_jwt({"sub": "a", "exp": NOW + 600}), now=NOW, max_lifetime_s=900)
    assert "long-lived" in describe_token(make_jwt({"sub": "a", "exp": NOW + 600}), now=NOW, max_lifetime_s=300)


def test_header_parameters_that_name_key_material_are_flagged():
    def with_header(h):
        enc = base64.urlsafe_b64encode(json.dumps(h).encode()).rstrip(b"=").decode()
        _, payload, sig = make_jwt({"sub": "a", "exp": NOW + 60}).split(".")
        return f"{enc}.{payload}.{sig}"

    found = describe_token(with_header({"alg": "RS256", "kid": "../../dev/null", "jku": "http://x.example/jwks"}), now=NOW)
    assert "untrusted-header:kid" in found and "untrusted-header:jku" in found
    assert "untrusted-header:x5u" not in found and "untrusted-header:jwk" not in found


def test_sensitive_claims_are_found_by_whole_word_even_when_nested():
    payload = {"sub": "a", "exp": NOW + 60, "company": "SandPay", "data": {"id": 25, "password": "x", "role": "customer"},
               "card_number": "tok_1", "password_hash": "h"}
    found = describe_token(make_jwt(payload), now=NOW)
    assert "sensitive-claim:data.password" in found
    assert "sensitive-claim:card_number" in found and "sensitive-claim:password_hash" in found
    assert not any(f.endswith("company") or f.endswith("data.id") or f.endswith("data.role") for f in found)
    assert found == sorted(set(found))


def test_a_real_token_from_the_portal_is_readable_by_anyone_who_holds_it():
    with serve(make_app()) as base:
        token = requests.post(f"{base}/api/login", json={"email": "alice@shop-a.example", "password": "alice-pass-1"},
                              timeout=5).json()["token"]
    jwt = decode_token(token)
    assert jwt.payload["sub"] == "alice@shop-a.example"
    assert jwt.header["alg"] == "HS256"
    assert describe_token(token, now=time.time()) == []
