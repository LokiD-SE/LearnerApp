"""Checks exercises/api/jwt_probe.py against the loopback portal: it must find the alg=none flaw on make_app()
and stay quiet on make_app({"jwt-none"})."""

import base64
import json

import pytest
from api.jwt_probe import (SPELLINGS, b64url_encode, forge_tampered, forge_unsigned, get_token, probe_alg_none)
from sandpay_vuln import make_app, serve

pytestmark = pytest.mark.exercise

ALICE = ("alice@shop-a.example", "alice-pass-1")
OPS = "ops@sandpay.example"


def _decode(part):
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def test_forge_unsigned_has_an_empty_signature_after_a_trailing_dot():
    token = forge_unsigned({"sub": OPS}, alg="NoNe")
    header, payload, signature = token.split(".")
    assert token.endswith(".") and signature == ""
    assert _decode(header) == {"alg": "NoNe", "typ": "JWT"}
    assert _decode(payload) == {"sub": OPS}
    assert "=" not in token  # base64url without padding


def test_forge_tampered_keeps_the_header_and_the_old_signature():
    with serve(make_app()) as base:
        token = get_token(base, *ALICE)
    forged = forge_tampered(token, {"sub": OPS})
    (h1, p1, s1), (h2, p2, s2) = token.split("."), forged.split(".")
    assert (h2, s2) == (h1, s1) and p2 != p1
    assert _decode(p2)["sub"] == OPS and _decode(p2)["exp"] == _decode(p1)["exp"]


def test_b64url_encode_strips_padding():
    assert b64url_encode(b"a") == "YQ" and b64url_encode(b"\xfb\xff") == "-_8"


def test_alg_none_found_on_the_vulnerable_portal():
    with serve(make_app()) as base:
        r = probe_alg_none(base, get_token(base, *ALICE), OPS)
    assert r.vulnerable is True
    assert r.accepted_spellings == ["none"]  # only the exact spelling: the other spellings fail on this portal
    assert r.victim_role == "admin"
    assert r.tampered_rejected is True  # the signature IS checked for signed tokens; the flaw is trusting alg
    assert r.baseline_status == 401


def test_quiet_when_alg_none_is_fixed():
    with serve(make_app({"jwt-none"})) as base:
        r = probe_alg_none(base, get_token(base, *ALICE), OPS)
    assert r.vulnerable is False
    assert r.accepted_spellings == [] and r.victim_role is None
    assert r.tampered_rejected is True


def test_quiet_when_every_flaw_but_jwt_none_is_still_open():
    # no false positive from other flaws: only jwt-none is closed, the rest stay vulnerable
    with serve(make_app({"jwt-none"})) as base:
        r = probe_alg_none(base, get_token(base, "bob@shop-b.example", "bob-pass-2"), OPS)
    assert r.vulnerable is False


def test_every_spelling_is_tried():
    assert SPELLINGS[0] == "none" and {"None", "NONE"} <= set(SPELLINGS)


def test_probe_refuses_to_conclude_when_the_endpoint_does_not_authenticate():
    with serve(make_app()) as base:
        token = get_token(base, *ALICE)
        with pytest.raises(RuntimeError):
            probe_alg_none(base, token, OPS, path="/health")  # answers 200 to everyone


def test_probe_refuses_to_conclude_when_the_valid_token_is_refused():
    with serve(make_app()) as base:
        with pytest.raises(RuntimeError):
            probe_alg_none(base, forge_unsigned({"sub": "nobody@x.example"}, alg="HS512"), OPS)


def test_get_token_raises_on_a_failed_sign_in():
    with serve(make_app()) as base:
        with pytest.raises(RuntimeError):
            get_token(base, "alice@shop-a.example", "wrong-password")
