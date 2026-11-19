import pytest
from foundations.http_cors import browser_allows_read, origin_of, probe_cors, same_origin

pytestmark = pytest.mark.exercise

PORTAL = "https://portal.sandpay.example"
UNTRUSTED = ["https://evil.example", "https://portal.sandpay.example.evil.example"]


# Server policies a tester might meet; each takes the request's Origin and returns the response headers.
def allowlist(origin):
    if origin == PORTAL:
        return {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Credentials": "true", "Vary": "Origin"}
    return {}


def reflect_with_credentials(origin):
    return {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Credentials": "true", "Vary": "Origin"}


def reflect_without_vary(origin):
    return {"Access-Control-Allow-Origin": origin}


def public_wildcard(origin):
    return {"Access-Control-Allow-Origin": "*"}


def suffix_check(origin):
    # Flawed allow-list: "starts with our origin" also matches portal.sandpay.example.evil.example
    if origin.startswith(PORTAL):
        return {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Credentials": "true", "Vary": "Origin"}
    return {}


def null_allowed(origin):
    if origin in (PORTAL, "null"):
        return {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Credentials": "true", "Vary": "Origin"}
    return {}


@pytest.mark.parametrize("url,expected", [
    ("https://portal.sandpay.example/dir/page", ("https", "portal.sandpay.example", 443)),
    ("http://Portal.SandPay.example", ("http", "portal.sandpay.example", 80)),
    ("https://portal.sandpay.example:8443/x", ("https", "portal.sandpay.example", 8443)),
])
def test_origin_tuple(url, expected):
    assert origin_of(url) == expected


def test_origin_of_rejects_non_http_urls():
    with pytest.raises(ValueError):
        origin_of("file:///etc/hosts")


@pytest.mark.parametrize("a,b,same", [
    ("https://portal.sandpay.example/a", "https://portal.sandpay.example/b?x=1", True),
    ("https://portal.sandpay.example", "https://portal.sandpay.example:443/", True),
    ("https://portal.sandpay.example", "http://portal.sandpay.example", False),
    ("https://portal.sandpay.example", "https://api.sandpay.example", False),
    ("http://portal.sandpay.example", "http://portal.sandpay.example:8080", False),
])
def test_same_origin(a, b, same):
    assert same_origin(a, b) is same


def test_browser_read_rules():
    o = "https://shop.example"
    assert browser_allows_read(o, {"Access-Control-Allow-Origin": "*"}, credentialed=False)
    assert not browser_allows_read(o, {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Credentials": "true"},
                                   credentialed=True)
    assert browser_allows_read(o, {"access-control-allow-origin": o, "access-control-allow-credentials": "true"},
                               credentialed=True)
    assert not browser_allows_read(o, {"Access-Control-Allow-Origin": o}, credentialed=True)
    assert not browser_allows_read(o, {"Access-Control-Allow-Origin": "https://other.example"}, credentialed=False)
    assert not browser_allows_read(o, {}, credentialed=False)


def test_allowlist_has_no_findings():
    assert probe_cors(allowlist, UNTRUSTED) == []


def test_reflection_with_credentials():
    assert probe_cors(reflect_with_credentials, UNTRUSTED) == [
        "allows-null-origin", "reflects-untrusted-origin-with-credentials"]


def test_reflection_without_vary():
    assert probe_cors(reflect_without_vary, UNTRUSTED) == [
        "allows-null-origin", "missing-vary-origin", "reflects-untrusted-origin"]


def test_public_wildcard_is_reported_for_triage():
    assert probe_cors(public_wildcard, UNTRUSTED) == ["wildcard-origin"]


def test_prefix_match_allow_list_is_bypassed():
    assert probe_cors(suffix_check, UNTRUSTED) == ["reflects-untrusted-origin-with-credentials"]
    assert probe_cors(suffix_check, ["https://evil.example"]) == []  # a probe set without the trick misses it


def test_null_origin():
    assert probe_cors(null_allowed, UNTRUSTED) == ["allows-null-origin"]
