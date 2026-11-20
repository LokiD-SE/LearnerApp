"""Checks practice/security/exercises/web/auth_throttling.py (testing-authentication lesson)."""

import pytest
import requests
from sandpay_vuln import make_app, serve
from web.auth_throttling import MAX_ATTEMPTS_CAP, classify, probe_login_throttling

pytestmark = pytest.mark.exercise

EMAIL = "alice@shop-a.example"
WRONG = [f"guess-{i}" for i in range(1, 31)]


class Spy(requests.Session):
    """A session that records every request it is asked to send."""

    def __init__(self):
        super().__init__()
        self.sent = []

    def request(self, method, url, *args, **kwargs):
        self.sent.append((method, url))
        return super().request(method, url, *args, **kwargs)


def test_vulnerable_portal_answers_every_guess():
    with serve(make_app()) as base:
        result = probe_login_throttling(base, EMAIL, WRONG, max_attempts=10)
    assert result["attempts"] == 10
    assert result["statuses"] == [401] * 10
    assert result["throttled"] is False and result["throttled_after"] is None and result["found"] is None
    assert classify(result) == "missing-rate-limit"


def test_fixed_portal_throttles_and_the_probe_stops():
    with serve(make_app({"no-rate-limit"})) as base:
        result = probe_login_throttling(base, EMAIL, WRONG, max_attempts=10)
    assert result["statuses"] == [401] * 5 + [429], result["statuses"]
    assert result["attempts"] == 6, "the probe must stop at the first 429"
    assert result["throttled"] is True and result["throttled_after"] == 5
    assert result["retry_after"] == "60"
    assert classify(result) == "throttled"


def test_stops_at_the_password_that_works():
    words = ["guess-1", "guess-2", "alice-pass-1", "guess-4"]
    with serve(make_app()) as base:
        result = probe_login_throttling(base, EMAIL, words, max_attempts=10)
    assert result["found"] == "alice-pass-1" and result["attempts"] == 3
    assert classify(result) == "password-found"


def test_never_sends_more_than_max_attempts():
    spy = Spy()
    with serve(make_app()) as base:
        result = probe_login_throttling(base, EMAIL, WRONG, max_attempts=4, session=spy)
    assert len(spy.sent) == 4 and result["attempts"] == 4
    assert classify(result) == "inconclusive"  # 4 normal answers are not enough evidence


@pytest.mark.parametrize("bad", [0, MAX_ATTEMPTS_CAP + 1])
def test_max_attempts_is_bounded(bad):
    with pytest.raises(ValueError):
        probe_login_throttling("http://127.0.0.1:9", EMAIL, WRONG, max_attempts=bad)


def test_refuses_other_hosts_before_sending_anything():
    spy = Spy()
    with pytest.raises(ValueError):
        probe_login_throttling("http://portal.sandpay.example", EMAIL, WRONG, session=spy)
    assert spy.sent == []


def test_classify_thresholds():
    base = {"statuses": [], "throttled": False, "throttled_after": None, "retry_after": None, "found": None}
    assert classify({**base, "attempts": 9}, min_attempts=10) == "inconclusive"
    assert classify({**base, "attempts": 10}, min_attempts=10) == "missing-rate-limit"
