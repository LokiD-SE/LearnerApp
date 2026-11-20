"""Checks practice/security/exercises/web/crypto_exposure_scan.py (testing-cryptography-and-data-exposure lesson)."""

import pytest
import requests
from sandpay_vuln import make_app, serve
from web.crypto_exposure_scan import excess_fields, find_secrets, scan_portal

pytestmark = pytest.mark.exercise

SECRET = "sk_test_shop_a_practice"
IBAN = "XX00 SAND 0000 0001"


def token(base):
    r = requests.post(base + "/api/login", json={"email": "alice@shop-a.example", "password": "alice-pass-1"}, timeout=10)
    assert r.status_code == 200
    return r.json()["token"]


def run(fixed=()):
    app = make_app(set(fixed))
    with serve(app) as base:
        return scan_portal(base, token(base), app.access_log)


def kinds(findings):
    return sorted({f["kind"] for f in findings})


def test_find_secrets_redacts_what_it_finds():
    text = f'{{"api_secret": "{SECRET}", "payout_iban": "{IBAN}"}}'
    assert find_secrets(text) == [{"kind": "api-key", "sample": "sk_t...(23 chars)"},
                                  {"kind": "iban", "sample": "XX00...(19 chars)"}]


def test_values_after_the_equals_sign_are_the_secret():
    lines = "login attempt email=alice@shop-a.example password=alice-pass-1\nkey=sandpay-practice-only-jwt-key"
    assert find_secrets(lines) == [{"kind": "password-in-log", "sample": "alic...(12 chars)"},
                                   {"kind": "secret-assignment", "sample": "sand...(29 chars)"}]


def test_stack_traces_and_ordinary_text():
    assert find_secrets("Traceback (most recent call last):\n  File x") == [{"kind": "stack-trace", "sample": "Trac...(33 chars)"}]
    assert find_secrets("GET /health 200\nlogin attempt email=alice@shop-a.example") == []
    assert find_secrets('{"payout_iban_last4": "0001", "id": "m_100"}') == []
    assert find_secrets("task_sk_ and sk_ alone") == []


def test_one_entry_per_match_sorted():
    found = find_secrets("password=bbbb2222 then password=aaaa1111")
    assert [f["sample"] for f in found] == ["aaaa...(8 chars)", "bbbb...(8 chars)"]


def test_excess_fields():
    body = {"id": "m_100", "name": "Shop A", "api_secret": SECRET, "payout_iban": IBAN}
    assert excess_fields(body, {"id", "name", "payout_iban_last4"}) == ["api_secret", "payout_iban"]
    assert excess_fields({"id": "m_100"}, {"id", "name"}) == []


def test_the_vulnerable_portal_leaks_through_all_three_channels():
    found = run()
    assert kinds(found["merchant"]) == ["api-key", "iban"]
    assert kinds(found["error"]) == ["secret-assignment", "stack-trace"]
    assert kinds(found["log"]) == ["password-in-log"]


def test_the_report_never_contains_a_whole_secret():
    text = str(run())
    for secret in (SECRET, "alice-pass-1", "sandpay-practice-only-jwt-key", "XX00 SAND 0000 0001"):
        assert secret not in text


@pytest.mark.parametrize("flaw,channel", [("data-exposure", "merchant"), ("verbose-errors", "error"), ("secret-logging", "log")])
def test_each_fix_silences_only_its_own_channel(flaw, channel):
    found = run({flaw})
    assert found[channel] == []
    assert all(found[other] for other in found if other != channel)


def test_no_false_positive_once_everything_is_fixed():
    assert run({"data-exposure", "verbose-errors", "secret-logging"}) == {"merchant": [], "error": [], "log": []}


def test_nothing_is_sent_to_a_non_loopback_url(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("a request was sent")

    monkeypatch.setattr(requests, "get", forbidden)
    monkeypatch.setattr(requests.Session, "request", forbidden)
    with pytest.raises(ValueError):
        scan_portal("https://api.sandpay.example", "t", [])
