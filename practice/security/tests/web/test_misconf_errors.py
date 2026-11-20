import pytest
from sandpay_vuln import make_app, serve
from web.misconf_errors import banner_discloses, classify_leaks, probe_errors, scan

pytestmark = pytest.mark.exercise

PY_TRACE = (
    "Traceback (most recent call last):\n"
    '  File "/srv/sandpay/portal.py", line 474, in handle\n'
    "    resp = self._route(req)\n"
    "RuntimeError: settlement batch failed\n"
)
PATHS = ["/health", "/boom", "/no-such-page"]


def test_generic_errors_leak_nothing():
    assert classify_leaks('{"error": "internal error", "reference": "716460f4"}') == []
    assert classify_leaks('{"error": "not found"}') == []
    assert classify_leaks('{"error": "missing or wrong CSRF token"}') == []


def test_python_traceback_gives_a_stack_trace_and_a_path():
    assert classify_leaks(PY_TRACE) == ["file-path", "stack-trace"]


def test_java_and_javascript_frames_are_stack_traces():
    assert classify_leaks("java.lang.NullPointerException\n\tat com.sandpay.Portal.charge(Portal.java:88)") == [
        "stack-trace"]
    assert classify_leaks("TypeError: x is undefined\n    at charge (app.js:10:5)") == ["stack-trace"]


def test_connection_strings_and_secrets():
    body = "db=postgresql://app:hunter2hunter2@db.internal:5432/sandpay key=sandpay-practice-only-jwt-key"
    assert classify_leaks(body) == ["connection-string", "secret"]
    assert classify_leaks("config: sk_practice_do_not_use") == ["secret"]


def test_database_errors_and_echoed_queries():
    assert classify_leaks("sqlite3.OperationalError: near \"'\": syntax error") == ["sql-error"]
    assert classify_leaks("failed: SELECT id FROM payments WHERE status = ''") == ["sql-error"]


def test_application_urls_are_not_file_paths():
    assert classify_leaks('{"error": "no such payment", "path": "/api/payments/9"}') == []
    assert classify_leaks("see https://docs.sandpay.example/errors/E12 for help") == []
    assert classify_leaks("failed to read /var/sandpay/portal.db") == ["file-path"]
    assert classify_leaks(r"missing C:\sandpay\config\app.ini") == ["file-path"]


def test_banner_with_a_version_discloses():
    assert banner_discloses({"Server": "SandPayPortal/0.9 Python/3.12"})
    assert banner_discloses({"server": "nginx/1.25.3"})
    assert banner_discloses({"Server": "Apache 2.4"})


def test_plain_banner_is_fine_and_x_powered_by_never_is():
    assert not banner_discloses({"Server": "SandPay"})
    assert not banner_discloses({"Server": "nginx"})
    assert not banner_discloses({})
    assert banner_discloses({"X-Powered-By": "Express"})


def test_probe_finds_the_leak_on_the_vulnerable_portal():
    with serve(make_app()) as base:
        leaks = probe_errors(base, PATHS)
    assert list(leaks) == ["/boom"]
    assert {"stack-trace", "file-path", "secret", "connection-string"} <= set(leaks["/boom"])


def test_probe_stays_quiet_when_verbose_errors_is_fixed():
    with serve(make_app({"verbose-errors"})) as base:
        assert probe_errors(base, PATHS) == {}


def test_scan_reports_leaks_and_the_banner_separately():
    with serve(make_app()) as base:
        result = scan(base, PATHS)
    assert result["banner"] is True and "/boom" in result["leaks"]


def test_each_flaw_is_closed_by_its_own_fix_only():
    with serve(make_app({"missing-headers"})) as base:  # the banner is gone, the traceback is not
        only_headers = scan(base, PATHS)
    with serve(make_app({"verbose-errors"})) as base:  # the traceback is gone, the banner is not
        only_errors = scan(base, PATHS)
    assert only_headers["banner"] is False and "/boom" in only_headers["leaks"]
    assert only_errors["banner"] is True and only_errors["leaks"] == {}
    with serve(make_app({"verbose-errors", "missing-headers"})) as base:
        assert scan(base, PATHS) == {"leaks": {}, "banner": False}
