import pytest
from foundations.http_headers import check_security_headers, fetch_headers, scan
from sandpay_vuln import make_app, serve

pytestmark = pytest.mark.exercise

GOOD = {
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Server": "SandPay",
}
PATHS = ["/health", "/search?q=refund", "/files?name=terms.txt", "/no-such-page"]


def test_good_headers_have_no_findings():
    assert check_security_headers(GOOD, https=True) == []


def test_header_names_are_case_insensitive():
    assert check_security_headers({k.lower(): v for k, v in GOOD.items()}, https=True) == []


def test_empty_response_on_https():
    assert check_security_headers({}, https=True) == [
        "missing-csp", "missing-frame-ancestors", "missing-hsts", "missing-nosniff", "missing-referrer-policy"]


def test_hsts_is_not_demanded_over_plain_http():
    no_sts = {k: v for k, v in GOOD.items() if k != "Strict-Transport-Security"}
    assert check_security_headers(no_sts, https=False) == []


@pytest.mark.parametrize("value", ["max-age=0", "includeSubDomains", "max-age=abc"])
def test_invalid_hsts(value):
    assert check_security_headers({**GOOD, "Strict-Transport-Security": value}, https=True) == ["invalid-hsts"]


def test_default_src_does_not_stop_framing():
    headers = {**GOOD, "Content-Security-Policy": "default-src 'none'"}
    assert check_security_headers(headers, https=True) == ["missing-frame-ancestors"]


def test_x_frame_options_also_stops_framing():
    headers = {**GOOD, "Content-Security-Policy": "default-src 'self'", "X-Frame-Options": "DENY"}
    assert check_security_headers(headers, https=True) == []


def test_nosniff_must_be_the_value():
    assert check_security_headers({**GOOD, "X-Content-Type-Options": "yes"}, https=True) == ["missing-nosniff"]


@pytest.mark.parametrize("name,value", [("Server", "nginx/1.27.4"), ("X-Powered-By", "Express 5.1")])
def test_version_disclosure(name, value):
    assert check_security_headers({**GOOD, name: value}, https=True) == ["version-disclosure"]


def test_fetch_headers_reads_error_responses_too():
    with serve(make_app()) as base:
        headers = fetch_headers(base + "/no-such-page")
    assert "Content-Type" in headers


def test_scan_finds_missing_headers_on_every_page_of_the_vulnerable_portal():
    with serve(make_app()) as base:
        report = scan(base, PATHS)
    assert sorted(report) == sorted(PATHS)
    for findings in report.values():
        assert findings == ["missing-csp", "missing-frame-ancestors", "missing-nosniff", "missing-referrer-policy",
                            "version-disclosure"]


def test_scan_is_quiet_when_the_portal_is_fixed():
    with serve(make_app({"missing-headers"})) as base:
        assert scan(base, PATHS) == {}
