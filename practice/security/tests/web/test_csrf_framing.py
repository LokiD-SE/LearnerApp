import pytest
from sandpay_vuln import make_app, serve
from web.csrf_framing import Origin, framable_pages, may_frame, source_matches, xfo_values

pytestmark = pytest.mark.exercise

PAGE = "https://portal.sandpay.example/settings"
SELF = "https://portal.sandpay.example"
EVIL = "https://evil.example"


@pytest.mark.parametrize("source, ancestor, expected", [
    ("'none'", SELF, False),
    ("'self'", SELF, True),
    ("'self'", "http://portal.sandpay.example", False),  # scheme differs, so not the same origin
    ("*", EVIL, True),
    ("https:", EVIL, True),
    ("https:", "http://evil.example", False),
    ("http:", "https://evil.example", True),  # http: also allows https
    ("https://partner.example", "https://partner.example", True),
    ("https://partner.example", "https://partner.example:8443", False),
    ("https://partner.example:8443", "https://partner.example:8443", True),
    ("https://partner.example:*", "https://partner.example:9000", True),
    ("partner.example", "http://partner.example", True),
    ("https://*.partner.example", "https://shop.partner.example", True),
    ("https://*.partner.example", "https://partner.example", False),  # the wildcard needs a subdomain
    ("https://partner.example/embed/", "https://partner.example", True),  # paths ignored for ancestors
    ("HTTPS://PARTNER.EXAMPLE", "https://partner.example", True),
])
def test_source_matching(source, ancestor, expected):
    assert source_matches(source, Origin.parse(ancestor), Origin.parse(PAGE)) is expected


def test_xfo_values_split_lower_and_dedupe():
    headers = [("X-Frame-Options", "SAMEORIGIN, sameorigin"), ("x-frame-options", "DENY,")]
    assert xfo_values(headers) == ["sameorigin", "deny", ""]


# The HTML standard's own tables for X-Frame-Options (section 7.7), framed cross-origin and same-origin.
@pytest.mark.parametrize("values, cross, same", [
    (["DENY"], False, False),
    (["SAMEORIGIN"], False, True),
    (["INVALID"], True, True),
    (["ALLOWALL"], True, True),
    (["ALLOW-FROM=https://example.com/"], True, True),
    (["SAMEORIGIN, SAMEORIGIN"], False, True),
    (["SAMEORIGIN, DENY"], False, False),
    (["SAMEORIGIN,"], False, False),
    (["SAMEORIGIN, ALLOWALL"], False, False),
    (["SAMEORIGIN, INVALID"], False, False),
    (["ALLOWALL, INVALID"], False, False),
    (["ALLOWALL,"], False, False),
    (["INVALID, INVALID"], True, True),
    (["SAMEORIGIN", "DENY"], False, False),  # two headers behave like one comma-separated header
])
def test_x_frame_options_per_the_html_standard(values, cross, same):
    headers = [("X-Frame-Options", v) for v in values]
    assert may_frame(headers, PAGE, [EVIL]).allowed is cross
    assert may_frame(headers, PAGE, [SELF]).allowed is same


def test_no_headers_allows_framing():
    d = may_frame([("Content-Type", "text/html")], PAGE, [EVIL])
    assert (d.allowed, d.by) == (True, "none")


def test_frame_ancestors_overrides_x_frame_options():
    headers = [("X-Frame-Options", "DENY"), ("Content-Security-Policy", "frame-ancestors https://partner.example")]
    d = may_frame(headers, PAGE, ["https://partner.example"])
    assert (d.allowed, d.by) == (True, "frame-ancestors")
    assert may_frame(headers, PAGE, [EVIL]).allowed is False


def test_report_only_does_not_protect():
    headers = [("Content-Security-Policy-Report-Only", "frame-ancestors 'none'")]
    assert may_frame(headers, PAGE, [EVIL]).allowed is True


def test_default_src_does_not_cover_framing():
    assert may_frame([("Content-Security-Policy", "default-src 'none'")], PAGE, [EVIL]).allowed is True


def test_every_policy_must_allow():
    headers = [("Content-Security-Policy", "frame-ancestors *"), ("Content-Security-Policy", "frame-ancestors 'self'")]
    assert may_frame(headers, PAGE, [EVIL]).allowed is False
    assert may_frame(headers, PAGE, [SELF]).allowed is True


def test_every_ancestor_is_checked():
    headers = [("Content-Security-Policy", "frame-ancestors 'self'")]
    assert may_frame(headers, PAGE, [SELF, EVIL]).allowed is False  # evil.example frames our own framing page
    assert may_frame([("X-Frame-Options", "SAMEORIGIN")], PAGE, [SELF, EVIL]).allowed is False


PATHS = ["/search?q=refund", "/login", "/health", "/no-such-page"]


def test_finds_framable_pages_on_the_vulnerable_portal():
    with serve(make_app()) as base:
        assert framable_pages(base, PATHS) == PATHS


def test_quiet_when_frame_ancestors_is_sent():
    with serve(make_app({"missing-headers"})) as base:
        assert framable_pages(base, PATHS) == []
