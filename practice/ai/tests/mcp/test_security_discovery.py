import pytest
from mcp.security_discovery import (
    MetadataError,
    as_metadata_urls,
    is_safe_oauth_url,
    metadata_url,
    parse_www_authenticate,
    protected_resource_metadata,
    select_scopes,
    step_up_scopes,
    validate_resource_metadata,
    www_authenticate,
)

pytestmark = pytest.mark.exercise

RESOURCE = "https://mcp.sandpay.example/mcp"
PRM = "https://mcp.sandpay.example/.well-known/oauth-protected-resource/mcp"


# --- server side -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "resource, expected",
    [
        (RESOURCE, PRM),
        ("https://mcp.sandpay.example", "https://mcp.sandpay.example/.well-known/oauth-protected-resource"),
        ("https://mcp.sandpay.example/", "https://mcp.sandpay.example/.well-known/oauth-protected-resource"),
        ("https://example.com/public/mcp", "https://example.com/.well-known/oauth-protected-resource/public/mcp"),
        ("https://mcp.sandpay.example:8443/mcp", "https://mcp.sandpay.example:8443/.well-known/oauth-protected-resource/mcp"),
    ],
)
def test_metadata_url(resource, expected):
    assert metadata_url(resource) == expected


def test_protected_resource_metadata():
    doc = protected_resource_metadata(RESOURCE, ["https://auth.sandpay.example"], ["payments:read"], "SandPay merchant tools")
    assert doc == {
        "resource": RESOURCE,
        "authorization_servers": ["https://auth.sandpay.example"],
        "scopes_supported": ["payments:read"],
        "bearer_methods_supported": ["header"],
        "resource_name": "SandPay merchant tools",
    }
    assert list(doc) == ["resource", "authorization_servers", "scopes_supported", "bearer_methods_supported", "resource_name"]
    assert "resource_name" not in protected_resource_metadata(RESOURCE, ("https://auth.sandpay.example",), ())


def test_metadata_needs_an_authorization_server():
    with pytest.raises(ValueError):
        protected_resource_metadata(RESOURCE, [], ["payments:read"])


def test_metadata_must_not_advertise_offline_access():
    with pytest.raises(ValueError):
        protected_resource_metadata(RESOURCE, ["https://auth.sandpay.example"], ["payments:read", "offline_access"])


def test_401_challenge_without_token():
    assert www_authenticate(PRM, scope=["payments:read"]) == f'Bearer scope="payments:read", resource_metadata="{PRM}"'
    assert www_authenticate(PRM) == f'Bearer resource_metadata="{PRM}"'
    # no error -> no error_description either
    assert www_authenticate(PRM, description="x") == f'Bearer resource_metadata="{PRM}"'


def test_403_insufficient_scope_challenge():
    header = www_authenticate(
        PRM, error="insufficient_scope", scope=["refunds:write", "payments:read"], description="Refunds need refunds:write"
    )
    assert header == (
        'Bearer error="insufficient_scope", scope="refunds:write payments:read", '
        f'resource_metadata="{PRM}", error_description="Refunds need refunds:write"'
    )


def test_challenge_escapes_quotes():
    header = www_authenticate(PRM, error="invalid_token", description='token "abc" expired')
    assert header.endswith('error_description="token \\"abc\\" expired"')


# --- client side -----------------------------------------------------------------------------------------


def test_parse_round_trip():
    header = www_authenticate(PRM, error="insufficient_scope", scope=["a:b", "c:d"], description='say "hi", ok')
    assert parse_www_authenticate(header) == {
        "scheme": "bearer",
        "error": "insufficient_scope",
        "scope": "a:b c:d",
        "resource_metadata": PRM,
        "error_description": 'say "hi", ok',
    }


def test_parse_spec_example_with_line_break_and_tokens():
    header = 'Bearer resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource",\n    scope="files:read", Error=invalid_token'
    got = parse_www_authenticate(header)
    assert got["resource_metadata"] == "https://mcp.example.com/.well-known/oauth-protected-resource"
    assert got["scope"] == "files:read"
    assert got["error"] == "invalid_token"


def test_parse_rejects_other_schemes():
    with pytest.raises(ValueError):
        parse_www_authenticate('Basic realm="x"')


@pytest.mark.parametrize(
    "url",
    ["https://auth.sandpay.example", "https://auth.sandpay.example/tenant1/authorize?x=1", "HTTPS://Auth.SandPay.Example"],
)
def test_safe_urls(url):
    assert is_safe_oauth_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://auth.sandpay.example",
        "javascript:alert(1)",
        "data:text/html,hi",
        "file:///etc/passwd",
        "https://169.254.169.254/latest/meta-data/",
        "https://10.0.0.1/api",
        "https://192.168.1.1/admin",
        "https://172.16.4.2",
        "https://127.0.0.1/token",
        "https://[::1]/token",
        "https://[fe80::1]/x",
        "https://[fd00::5]/x",
        "https://[::ffff:10.0.0.1]/x",
        "https://0.0.0.0/",
        "https://localhost:6379/",
        "https:///nohost",
        "https://[not-an-ip/x",
    ],
)
def test_unsafe_urls(url):
    assert not is_safe_oauth_url(url)


def test_loopback_http_only_when_allowed():
    for url in ["http://localhost:8080/callback", "http://127.0.0.1:9000", "http://[::1]:9000", "https://localhost/x"]:
        assert not is_safe_oauth_url(url)
        assert is_safe_oauth_url(url, allow_loopback_http=True)
    assert not is_safe_oauth_url("http://auth.sandpay.example", allow_loopback_http=True)
    assert not is_safe_oauth_url("http://10.0.0.1", allow_loopback_http=True)


def test_validate_resource_metadata_ok():
    doc = protected_resource_metadata(RESOURCE, ["https://auth.sandpay.example"], ["payments:read"])
    assert validate_resource_metadata(doc, expected_resource=RESOURCE) == ["https://auth.sandpay.example"]


@pytest.mark.parametrize(
    "doc",
    [
        {"resource": "https://mcp.sandpay.example/mcp/", "authorization_servers": ["https://auth.sandpay.example"]},
        {"resource": "https://MCP.sandpay.example/mcp", "authorization_servers": ["https://auth.sandpay.example"]},
        {"resource": "https://evil.example/mcp", "authorization_servers": ["https://auth.sandpay.example"]},
        {"resource": RESOURCE},
        {"resource": RESOURCE, "authorization_servers": []},
        {"resource": RESOURCE, "authorization_servers": "https://auth.sandpay.example"},
        {"resource": RESOURCE, "authorization_servers": ["http://169.254.169.254/latest"]},
        {"resource": RESOURCE, "authorization_servers": ["https://auth.sandpay.example", "javascript:alert(1)"]},
        {"resource": RESOURCE, "authorization_servers": [7]},
    ],
)
def test_validate_resource_metadata_rejects(doc):
    with pytest.raises(MetadataError):
        validate_resource_metadata(doc, expected_resource=RESOURCE)


def test_as_metadata_urls_with_path():
    assert as_metadata_urls("https://auth.example.com/tenant1") == [
        "https://auth.example.com/.well-known/oauth-authorization-server/tenant1",
        "https://auth.example.com/.well-known/openid-configuration/tenant1",
        "https://auth.example.com/tenant1/.well-known/openid-configuration",
    ]


def test_as_metadata_urls_without_path():
    expected = [
        "https://auth.example.com/.well-known/oauth-authorization-server",
        "https://auth.example.com/.well-known/openid-configuration",
    ]
    assert as_metadata_urls("https://auth.example.com") == expected
    assert as_metadata_urls("https://auth.example.com/") == expected


def test_select_scopes():
    assert select_scopes("payments:read", ["payments:read", "refunds:write"]) == "payments:read"
    assert select_scopes(None, ["payments:read", "refunds:write"]) == "payments:read refunds:write"
    assert select_scopes("", ("payments:read",)) == "payments:read"
    assert select_scopes(None, None) is None
    assert select_scopes(None, []) is None


def test_step_up_keeps_previous_scopes():
    assert step_up_scopes("payments:read", "refunds:write") == "payments:read refunds:write"
    assert step_up_scopes("refunds:write payments:read", "payments:read") == "payments:read refunds:write"
    assert step_up_scopes(None, "refunds:write") == "refunds:write"
    assert step_up_scopes("", "") == ""
