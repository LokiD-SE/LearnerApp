"""Checks exercises/foundations/recon_fingerprint.py: banner grabbing and page-content leaks
(WSTG-INFO-02, -05, -08). The first three Server values are the examples in WSTG-INFO-02."""

import pytest
from foundations.recon_fingerprint import Finding, fingerprint, scan
from sandpay_vuln import make_app, serve

pytestmark = pytest.mark.exercise


@pytest.mark.parametrize("server", ["Apache/2.4.43 (Unix)", "nginx/1.31.5", "lighttpd/1.4.85",
                                    "SandPayPortal/0.9 Python/3.12"])
def test_versioned_server_banner(server):
    assert fingerprint({"Server": server}) == [Finding("server-version", server)]


@pytest.mark.parametrize("server", ["SandPay", "nginx", "cloudflare", ""])
def test_product_name_without_version_is_not_reported(server):
    assert fingerprint({"Server": server}) == []


def test_header_names_are_case_insensitive():
    found = fingerprint({"server": "nginx/1.31.5", "x-powered-by": "Mono"})
    assert found == [Finding("server-version", "nginx/1.31.5"), Finding("powered-by", "Mono")]


def test_stack_trace_reports_its_last_line():
    body = 'Traceback (most recent call last):\n  File "app.py", line 3, in boom\nValueError: bad batch\n'
    assert fingerprint({"Content-Type": "text/plain"}, body) == [Finding("stack-trace", "ValueError: bad batch")]


def test_html_comments_only_in_html():
    page = "<!doctype html><!-- TODO remove /internal/admin before go-live --><p>Hi</p><!--build 42-->"
    assert fingerprint({"Content-Type": "text/html; charset=utf-8"}, page) == [
        Finding("html-comment", "TODO remove /internal/admin before go-live"), Finding("html-comment", "build 42")]
    assert fingerprint({"Content-Type": "text/plain"}, page) == []


def test_scan_finds_the_portal_leaks():
    with serve(make_app()) as base:
        found = scan(base)
    assert [f.kind for f in found] == ["server-version", "stack-trace"]
    assert found[0].evidence == "SandPayPortal/0.9 Python/3.12"
    assert found[1].evidence.startswith("RuntimeError: settlement batch failed")


def test_scan_is_quiet_once_fixed():
    with serve(make_app({"missing-headers", "verbose-errors"})) as base:
        assert scan(base) == []


def test_scan_reports_only_what_is_still_open():
    with serve(make_app({"verbose-errors"})) as base:
        assert [f.kind for f in scan(base)] == ["server-version"]
