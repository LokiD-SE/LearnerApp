"""Checks exercises/api/jwt_validate.py: every verdict reason, then the portal's own token against a strict policy."""

import pytest
import requests
from api.jwt_validate import Policy, validate_token
from sandpay_vuln import JWT_SECRET, make_app, make_jwt, serve

pytestmark = pytest.mark.exercise

NOW = 1_800_000_000
ISS = "https://auth.sandpay.example"
AUD = "merchant-api"


def token(claims=None, alg="HS256", key=JWT_SECRET):
    return make_jwt({"sub": "alice@shop-a.example", "exp": NOW + 600, **(claims or {})}, alg=alg, key=key)


def reasons(tok, **policy):
    v = validate_token(tok, Policy(JWT_SECRET, **policy), NOW)
    assert v.ok == (v.reasons == [])
    return v.reasons


def test_a_good_token_is_accepted():
    v = validate_token(token(), Policy(JWT_SECRET), NOW)
    assert v.ok is True and v.reasons == []


@pytest.mark.parametrize("bad", ["abc", "a.b.c", "a.b", "e30.e30.e30.e30"])
def test_malformed_tokens(bad):
    assert reasons(bad) == ["malformed"]


def test_unsigned_tokens_are_never_accepted_whatever_the_claims():
    assert reasons(token(alg="none")) == ["alg-not-allowed"]


def test_algorithm_is_compared_exactly_against_the_allow_list():
    assert reasons(token(alg="hs256")) == ["alg-not-allowed"]  # alg is case-sensitive (RFC 7515)
    assert reasons(token(alg="HS384")) == ["alg-not-allowed"]  # valid-looking, but not on the list
    assert validate_token(token(), Policy(JWT_SECRET, algorithms=("HS256", "HS512")), NOW).ok


def test_signature_failures_stop_at_once_and_hide_the_claims():
    assert reasons(token(key=b"another-key")) == ["bad-signature"]
    h, p, s = token().split(".")
    forged = make_jwt({"sub": "ops@sandpay.example", "exp": NOW + 600}).split(".")[1]
    assert reasons(f"{h}.{forged}.{s}") == ["bad-signature"]
    assert reasons(f"{h}.{p}.") == ["bad-signature"]  # signature stripped
    assert reasons(f"{h}.{p}.!!!") == ["bad-signature"]
    # expired AND badly signed: only the signature is reported - claims of an unproven token are not read
    assert reasons(token({"exp": NOW - 9999}, key=b"another-key")) == ["bad-signature"]


def test_expiry_with_leeway():
    assert reasons(token({"exp": NOW - 30}), leeway_s=60) == []
    assert reasons(token({"exp": NOW - 61}), leeway_s=60) == ["expired"]
    assert reasons(token({"exp": NOW - 60}), leeway_s=60) == ["expired"]  # "on or after" exp, RFC 7519 4.1.4
    assert reasons(token({"exp": NOW - 1}), leeway_s=0) == ["expired"]


def test_not_before():
    assert reasons(token({"nbf": NOW + 30}), leeway_s=60) == []
    assert reasons(token({"nbf": NOW + 120}), leeway_s=60) == ["not-yet-valid"]
    assert reasons(token({"nbf": NOW}), leeway_s=0) == []


def test_required_claims():
    claims = {"sub": "a"}
    no_exp = make_jwt(claims)
    assert reasons(no_exp) == ["missing-exp"]
    assert reasons(no_exp, require=()) == []
    assert reasons(no_exp, require=("exp", "sub", "jti")) == ["missing-exp", "missing-jti"]


def test_issuer_must_match_exactly_and_be_present():
    assert reasons(token({"iss": ISS}), issuer=ISS) == []
    assert reasons(token(), issuer=ISS) == ["missing-iss"]
    assert reasons(token({"iss": "https://auth.sandpay.example.evil.test"}), issuer=ISS) == ["issuer-mismatch"]
    assert reasons(token({"iss": ISS + "/"}), issuer=ISS) == ["issuer-mismatch"]  # no prefix or substring matching


def test_audience_string_or_list():
    assert reasons(token({"aud": AUD}), audience=AUD) == []
    assert reasons(token({"aud": ["other-api", AUD]}), audience=AUD) == []
    assert reasons(token({"aud": "billing-api"}), audience=AUD) == ["audience-mismatch"]
    assert reasons(token({"aud": ["billing-api", "admin-api"]}), audience=AUD) == ["audience-mismatch"]
    assert reasons(token(), audience=AUD) == ["missing-aud"]
    assert reasons(token({"aud": "merchant-api-admin"}), audience=AUD) == ["audience-mismatch"]


def test_lifetime_cap_needs_both_claims():
    assert reasons(token({"iat": NOW, "exp": NOW + 900}), max_lifetime_s=900) == []
    assert reasons(token({"iat": NOW, "exp": NOW + 901}), max_lifetime_s=900) == ["lifetime-too-long"]
    assert reasons(token({"exp": NOW + 99999}), max_lifetime_s=900) == []  # no iat: nothing to measure


def test_wrongly_typed_time_claims_are_reported_not_crashed_on():
    assert reasons(token({"exp": "soon"})) == ["bad-claim:exp"]
    assert reasons(token({"exp": True})) == ["bad-claim:exp"]
    assert reasons(token({"nbf": "x"})) == ["bad-claim:nbf"]


def test_several_claim_problems_are_reported_together_in_a_stable_order():
    tok = token({"exp": NOW - 999, "aud": "billing-api", "iss": "https://evil.example"})
    assert reasons(tok, issuer=ISS, audience=AUD) == ["expired", "issuer-mismatch", "audience-mismatch"]


@pytest.mark.parametrize("algs", [("none",), ("HS256", "RS256"), ("None",)])
def test_a_policy_that_would_accept_none_or_unsupported_algorithms_is_refused(algs):
    with pytest.raises(ValueError):
        validate_token(token(), Policy(JWT_SECRET, algorithms=algs), NOW)


def test_the_portals_own_token_passes_a_basic_policy_but_fails_a_strict_one():
    import time

    with serve(make_app()) as base:
        tok = requests.post(f"{base}/api/login", json={"email": "alice@shop-a.example", "password": "alice-pass-1"},
                            timeout=5).json()["token"]
    now = time.time()
    assert validate_token(tok, Policy(JWT_SECRET), now).ok  # signed, unexpired
    strict = validate_token(tok, Policy(JWT_SECRET, issuer=ISS, audience=AUD), now)
    assert strict.reasons == ["missing-iss", "missing-aud"]  # it names no issuer and no audience


def test_a_forged_alg_none_token_is_what_the_vulnerable_portal_accepts_and_this_validator_refuses():
    forged = make_jwt({"sub": "ops@sandpay.example", "exp": NOW + 300}, alg="none")
    with serve(make_app()) as base:
        accepted = requests.get(f"{base}/api/me", headers={"Authorization": f"Bearer {forged}"}, timeout=5)
    assert accepted.status_code == 200  # the flaw
    assert validate_token(forged, Policy(JWT_SECRET), NOW).reasons == ["alg-not-allowed"]  # the check it lacks
