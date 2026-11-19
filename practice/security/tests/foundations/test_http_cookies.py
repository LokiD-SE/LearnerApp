import json
import urllib.request

import pytest
from foundations.http_cookies import audit_cookie, parse_set_cookie
from sandpay_vuln import make_app, serve

pytestmark = pytest.mark.exercise

STRONG = "__Host-SID=abc123; Path=/; Secure; HttpOnly; SameSite=Strict"


def login_cookie(base_url: str) -> str:
    body = json.dumps({"email": "alice@shop-a.example", "password": "alice-pass-1"}).encode()
    req = urllib.request.Request(base_url + "/api/login", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.headers["Set-Cookie"]


def test_parse_name_value_and_attributes():
    c = parse_set_cookie("sid=xyz; Path=/; secure; HTTPONLY; SameSite=Lax; Max-Age=600")
    assert (c.name, c.value) == ("sid", "xyz")
    assert c.attributes == {"path": "/", "secure": True, "httponly": True, "samesite": "Lax", "max-age": "600"}


def test_parse_rejects_a_header_without_a_name_value_pair():
    with pytest.raises(ValueError):
        parse_set_cookie("Secure; HttpOnly")


def test_strong_session_cookie_has_no_findings():
    assert audit_cookie(STRONG) == []


def test_bare_session_cookie_misses_everything():
    assert audit_cookie("sid=abc123; Path=/") == ["missing-httponly", "missing-samesite", "missing-secure"]


def test_secure_is_only_demanded_on_https():
    assert audit_cookie("sid=abc; Path=/; HttpOnly; SameSite=Lax", https=False) == []
    assert audit_cookie("sid=abc; Path=/; HttpOnly; SameSite=Lax", https=True) == ["missing-secure"]


def test_non_session_cookie_may_be_readable_by_script():
    assert audit_cookie("theme=dark; Path=/; Secure", session=False) == []


def test_samesite_none_needs_secure():
    assert "samesite-none-without-secure" in audit_cookie("sid=a; HttpOnly; SameSite=None", https=False)
    assert audit_cookie("sid=a; Secure; HttpOnly; SameSite=None") == []


def test_domain_on_a_session_cookie_widens_scope():
    assert audit_cookie("sid=a; Domain=sandpay.example; Path=/; Secure; HttpOnly; SameSite=Lax") == [
        "domain-widens-scope"]


@pytest.mark.parametrize("header", [
    "__Host-SID=1; Secure",                                   # no Path=/
    "__Host-SID=1; Path=/",                                   # not Secure
    "__Host-SID=1; Secure; Domain=site.example; Path=/",      # has Domain
])
def test_host_prefix_rules(header):
    assert "invalid-host-prefix" in audit_cookie(header, session=False)


def test_secure_prefix_needs_secure_and_prefix_is_case_sensitive():
    assert audit_cookie("__Secure-ID=1; Path=/", session=False, https=False) == ["invalid-secure-prefix"]
    assert audit_cookie("__secure-ID=1; Path=/", session=False, https=False) == []


def test_attribute_names_are_case_insensitive():
    assert audit_cookie("sid=a; path=/; SECURE; httponly; samesite=strict") == []


def test_finds_the_weak_session_cookie_on_the_vulnerable_portal():
    with serve(make_app()) as base:
        header = login_cookie(base)
    # The portal is plain HTTP on loopback; audit as if deployed on HTTPS, which is where it matters.
    assert audit_cookie(header, https=True) == ["missing-httponly", "missing-samesite", "missing-secure"]


def test_quiet_when_the_portal_is_fixed():
    with serve(make_app({"weak-session"})) as base:
        header = login_cookie(base)
    assert audit_cookie(header, https=True) == []
