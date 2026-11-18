import pytest
from mcp.security_tokens import (
    AuthError,
    InvalidResourceURI,
    TokenValidator,
    b64url_decode,
    b64url_encode,
    bearer_token,
    canonical_resource,
    sign_token,
)

pytestmark = pytest.mark.exercise

SECRET = b"sandpay-teaching-secret"
ISSUER = "https://auth.sandpay.example"
RESOURCE = "https://mcp.sandpay.example/mcp"
NOW = 1_800_000_000


def claims(**overrides):
    base = {
        "iss": ISSUER,
        "sub": "merchant-m204",
        "aud": RESOURCE,
        "exp": NOW + 300,
        "scope": "payments:read",
        "client_id": "https://client.example/metadata.json",
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def validator(**kw):
    kw.setdefault("clock", lambda: NOW)
    return TokenValidator(RESOURCE, ISSUER, SECRET, **kw)


def reason(excinfo):
    return excinfo.value.status, excinfo.value.error, excinfo.value.description


# --- canonical_resource ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "uri, expected",
    [
        ("https://mcp.sandpay.example/mcp", "https://mcp.sandpay.example/mcp"),
        ("HTTPS://MCP.SandPay.Example/mcp", "https://mcp.sandpay.example/mcp"),
        ("https://mcp.sandpay.example/", "https://mcp.sandpay.example"),
        ("https://mcp.sandpay.example/mcp/", "https://mcp.sandpay.example/mcp"),
        ("https://mcp.sandpay.example:8443", "https://mcp.sandpay.example:8443"),
        ("https://mcp.sandpay.example/Server/MCP", "https://mcp.sandpay.example/Server/MCP"),
    ],
)
def test_canonical_resource(uri, expected):
    assert canonical_resource(uri) == expected


@pytest.mark.parametrize(
    "uri", ["mcp.sandpay.example", "https://mcp.sandpay.example#frag", "https://mcp.sandpay.example/mcp#", "ftp://mcp.sandpay.example"]
)
def test_canonical_resource_rejects(uri):
    with pytest.raises(InvalidResourceURI):
        canonical_resource(uri)


# --- bearer_token ----------------------------------------------------------------------------------------


def test_bearer_token_extracts_the_token():
    assert bearer_token("Bearer abc.def.ghi") == "abc.def.ghi"
    assert bearer_token("bearer abc.def.ghi") == "abc.def.ghi"


@pytest.mark.parametrize("header", [None, "", "Basic dXNlcjpwYXNz"])
def test_no_credentials_is_401_without_error_code(header):
    with pytest.raises(AuthError) as e:
        bearer_token(header)
    assert (e.value.status, e.value.error) == (401, None)


@pytest.mark.parametrize("header", ["Bearer", "Bearer ", "Bearer one two"])
def test_malformed_bearer_is_invalid_request(header):
    with pytest.raises(AuthError) as e:
        bearer_token(header)
    assert (e.value.status, e.value.error) == (400, "invalid_request")


def test_token_in_query_string_is_refused():
    with pytest.raises(AuthError) as e:
        bearer_token("Bearer abc.def.ghi", "https://mcp.sandpay.example/mcp?access_token=abc.def.ghi")
    assert (e.value.status, e.value.error) == (400, "invalid_request")


# --- validate --------------------------------------------------------------------------------------------


def test_valid_token_returns_claims():
    got = validator().validate(sign_token(claims(), SECRET))
    assert got["sub"] == "merchant-m204"


def test_audience_list_and_canonical_forms_are_accepted():
    token = sign_token(claims(aud=["https://api.sandpay.example", "HTTPS://MCP.SANDPAY.EXAMPLE/mcp/"]), SECRET)
    assert validator().validate(token)["iss"] == ISSUER


@pytest.mark.parametrize(
    "aud", ["https://api.sandpay.example", ["https://api.sandpay.example"], "https://mcp.sandpay.example", None, 42]
)
def test_token_for_another_resource_is_rejected(aud):
    with pytest.raises(AuthError) as e:
        validator().validate(sign_token(claims(aud=aud), SECRET))
    assert reason(e) == (401, "invalid_token", "token not issued for this server")


def test_wrong_issuer_is_rejected():
    with pytest.raises(AuthError) as e:
        validator().validate(sign_token(claims(iss="https://auth.sandpay.example/"), SECRET))
    assert reason(e) == (401, "invalid_token", "wrong issuer")


def test_bad_signature_is_rejected():
    with pytest.raises(AuthError) as e:
        validator().validate(sign_token(claims(), b"another-secret"))
    assert reason(e) == (401, "invalid_token", "bad signature")


def test_tampered_payload_is_rejected():
    header, payload, sig = sign_token(claims(), SECRET).split(".")
    forged = b64url_encode(b64url_decode(payload).replace(b"payments:read", b"refunds:write"))
    with pytest.raises(AuthError) as e:
        validator().validate(f"{header}.{forged}.{sig}")
    assert reason(e)[2] == "bad signature"


def test_alg_none_is_rejected_even_when_unsigned():
    header = b64url_encode(b'{"alg":"none","typ":"at+jwt"}')
    payload = b64url_encode(b'{"iss":"https://auth.sandpay.example"}')
    with pytest.raises(AuthError) as e:
        validator().validate(f"{header}.{payload}.")
    assert reason(e)[2] == "unsupported algorithm"


def test_id_token_type_is_rejected():
    with pytest.raises(AuthError) as e:
        validator().validate(sign_token(claims(), SECRET, typ="JWT"))
    assert reason(e)[2] == "wrong token type"


def test_application_at_jwt_type_is_accepted():
    assert validator().validate(sign_token(claims(), SECRET, typ="application/at+jwt"))


@pytest.mark.parametrize("token", ["", "abc", "a.b", "a.b.c.d", "!!!.###.$$$", b64url_encode(b"[1]") + ".e30.x"])
def test_malformed_tokens(token):
    with pytest.raises(AuthError) as e:
        validator().validate(token)
    assert reason(e) == (401, "invalid_token", "malformed token")


def test_expiry_with_leeway():
    token = sign_token(claims(exp=NOW - 30), SECRET)
    assert validator(leeway_s=60).validate(token)
    with pytest.raises(AuthError) as e:
        validator(leeway_s=0).validate(token)
    assert reason(e)[2] == "token expired"
    with pytest.raises(AuthError):
        validator(leeway_s=0).validate(sign_token(claims(exp=NOW), SECRET))


@pytest.mark.parametrize("exp", [None, "1800000300", True])
def test_missing_or_non_numeric_exp_is_rejected(exp):
    with pytest.raises(AuthError) as e:
        validator().validate(sign_token(claims(exp=exp), SECRET))
    assert reason(e)[2] == "token expired"


def test_signature_checked_before_claims():
    # a forged token for another audience must fail on the signature, not leak which claim was wrong
    with pytest.raises(AuthError) as e:
        validator().validate(sign_token(claims(aud="https://evil.example"), b"attacker-key"))
    assert reason(e)[2] == "bad signature"


# --- require / authenticate ------------------------------------------------------------------------------


def test_require_passes_with_enough_scope():
    validator().require({"scope": "payments:read refunds:write"}, {"refunds:write"})


def test_insufficient_scope_lists_every_needed_scope():
    with pytest.raises(AuthError) as e:
        validator().require({"scope": "payments:read"}, {"refunds:write", "payments:read", "disputes:read"})
    assert (e.value.status, e.value.error) == (403, "insufficient_scope")
    assert e.value.scope == ("disputes:read", "payments:read", "refunds:write")


def test_scope_hierarchy():
    v = validator(implies={"merchant:admin": ["payments:read", "refunds:write"]})
    v.require({"scope": "merchant:admin"}, {"refunds:write"})
    with pytest.raises(AuthError):
        v.require({"scope": "payments:read"}, {"merchant:admin"})


def test_missing_scope_claim_means_no_scopes():
    with pytest.raises(AuthError):
        validator().require({}, {"payments:read"})


def test_authenticate_end_to_end():
    v = validator()
    token = sign_token(claims(scope="payments:read"), SECRET)
    assert v.authenticate(f"Bearer {token}", {"payments:read"})["sub"] == "merchant-m204"
    with pytest.raises(AuthError) as e:
        v.authenticate(f"Bearer {token}", {"refunds:write"})
    assert e.value.status == 403
    with pytest.raises(AuthError) as e:
        v.authenticate(None, {"payments:read"})
    assert e.value.status == 401
