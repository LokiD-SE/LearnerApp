import pytest
from foundations.fund_probe import Finding, leak_lines, probe_error_handling, redact
from sandpay_vuln import make_app, serve

pytestmark = pytest.mark.exercise


def test_finds_the_leak_on_the_vulnerable_portal():
    with serve(make_app()) as base:
        findings = probe_error_handling(base, ("/health", "/boom", "/no-such-page"))
    assert len(findings) == 1
    f = findings[0]
    assert isinstance(f, Finding)
    assert (f.check, f.status) == ("WSTG-ERRH-01", 500)
    assert f.url.endswith("/boom")
    assert f.evidence[0] == "Traceback (most recent call last):"
    assert f.evidence[-1] == ("RuntimeError: settlement batch failed; db=sqlite:///var/sandpay/portal.db "
                              "key=[REDACTED]")
    assert len(f.evidence) <= 3
    assert sum(line.startswith("File ") for line in f.evidence) == 0  # stack frames are not evidence


def test_evidence_never_contains_the_leaked_secret():
    with serve(make_app()) as base:
        (f,) = probe_error_handling(base)
    text = "\n".join(f.evidence)
    assert "sandpay-practice-only-jwt-key" not in text


def test_quiet_when_errors_are_handled():
    with serve(make_app({"verbose-errors"})) as base:
        assert probe_error_handling(base, ("/health", "/boom")) == []


def test_refuses_non_loopback_targets_before_sending():
    calls = []
    with pytest.raises(ValueError):
        probe_error_handling("https://portal.sandpay.example", get=lambda *a, **k: calls.append(a))
    assert calls == []


def test_redact_and_leak_lines():
    assert redact("db=x KEY=abc123; token=t-1") == "db=x KEY=[REDACTED]; token=[REDACTED]"
    body = "ok\n  File \"/app/x.py\", line 3\nplain\nError: password=hunter2\nmore\n\tat a.b\n\tat c.d"
    assert leak_lines(body) == ['File "/app/x.py", line 3', "Error: password=[REDACTED]"]
    assert leak_lines("a=1\nsecret=s1\ntoken=t2\npassword=p3\nkey=k4") == [
        "secret=[REDACTED]", "token=[REDACTED]", "password=[REDACTED]"]
    assert leak_lines('{"error": "internal error", "reference": "a1b2c3d4"}') == []
