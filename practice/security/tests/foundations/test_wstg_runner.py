import pytest
from foundations.wstg_runner import (DEFAULT_CHECKS, Check, Result, check_csp_asvs, check_error_handling,
                                     combined_status, csp_problems, run_checks, to_checklist_markdown)
from sandpay_vuln import make_app, serve

pytestmark = pytest.mark.exercise


@pytest.fixture
def vulnerable():
    with serve(make_app()) as base:
        yield base


@pytest.fixture
def fixed():
    with serve(make_app({"verbose-errors", "missing-headers"})) as base:
        yield base


def test_error_handling_fails_on_the_vulnerable_portal(vulnerable):
    passed, evidence = check_error_handling(vulnerable)
    assert passed is False
    assert "500" in evidence and "Traceback" in evidence


def test_error_handling_passes_once_fixed(fixed):
    passed, evidence = check_error_handling(fixed)
    assert passed is True and "500" in evidence


@pytest.mark.parametrize("policy, problems", [
    (None, ["no policy"]),
    ("  ", ["no policy"]),
    ("default-src 'self'; frame-ancestors 'none'", ["object-src 'none' missing", "base-uri 'none' missing"]),
    ("default-src 'self'; object-src 'none'; base-uri 'none'", []),
    ("SCRIPT-SRC 'nonce-r4nd0m'; OBJECT-SRC 'none'; BASE-URI 'none'", []),
    ("object-src 'none'; base-uri 'none'", ["no allowlist, nonce or hash"]),
    ("default-src 'self'; object-src 'self'; base-uri 'none'", ["object-src 'none' missing"]),
])
def test_csp_problems(policy, problems):
    assert csp_problems(policy) == problems


def test_csp_check_against_both_portals(vulnerable, fixed):
    assert check_csp_asvs(vulnerable) == (False, "no policy")
    passed, evidence = check_csp_asvs(fixed)
    assert passed is False  # the portal's "fixed" CSP is still below the ASVS L2 minimum
    assert evidence == "object-src 'none' missing, base-uri 'none' missing"


def boom(_):
    raise ConnectionError("refused")


def test_a_crashed_check_is_an_error_not_a_pass(vulnerable):
    checks = [Check("WSTG-INFO-02", "Fingerprint Web Server", "v5.0.0-13.4.6", boom),
              Check("WSTG-ERRH-01", "Testing for Improper Error Handling", "v5.0.0-16.5.1", check_error_handling)]
    results = run_checks(vulnerable, checks)
    assert [r.status for r in results] == ["Error", "Fail"]
    assert results[0].evidence == "ConnectionError: refused"


def test_combined_status():
    assert combined_status(["Pass", "Fail", "Error"]) == "Fail"
    assert combined_status(["Pass", "Error"]) == "Error"
    assert combined_status(["Pass", "Pass"]) == "Pass"


def test_checklist_markdown(fixed):
    results = run_checks(fixed, DEFAULT_CHECKS)
    md = to_checklist_markdown(results)
    lines = md.splitlines()
    assert lines[0] == "| Test ID | Test Name | Status | Notes |"
    assert lines[1] == "|---|---|---|---|"
    assert lines[2].startswith("| WSTG-ERRH-01 | Testing for Improper Error Handling | Pass | v5.0.0-16.5.1: GET /boom 500")
    assert lines[3] == ("| (no WSTG test) | Content-Security-Policy minimum | Fail | v5.0.0-3.4.3: "
                        "object-src 'none' missing, base-uri 'none' missing |")
    assert md.endswith("\n") and len(lines) == 4


def test_checklist_groups_checks_of_one_test_and_sorts():
    ok = Check("WSTG-SESS-02", "Testing for Cookies Attributes", "v5.0.0-3.3.4", lambda b: (True, "HttpOnly"))
    bad = Check("WSTG-SESS-02", "Testing for Cookies Attributes", "v5.0.0-3.3.1", lambda b: (False, "no Secure"))
    first = Check("WSTG-ATHZ-04", "Testing for Insecure Direct Object References", "v5.0.0-8.2.2", lambda b: (True, "404"))
    md = to_checklist_markdown(run_checks("http://127.0.0.1:9", [ok, bad, first]))
    rows = md.splitlines()[2:]
    assert rows == [
        "| WSTG-ATHZ-04 | Testing for Insecure Direct Object References | Pass | v5.0.0-8.2.2: 404 |",
        "| WSTG-SESS-02 | Testing for Cookies Attributes | Fail | v5.0.0-3.3.4: HttpOnly; v5.0.0-3.3.1: no Secure |",
    ]
    assert isinstance(run_checks("x", [ok])[0], Result)
