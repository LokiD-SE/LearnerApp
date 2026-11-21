"""Checks exercises/api/logic_rate_limit.py against the loopback portal: it must find the missing limit on
make_app() and stay quiet on make_app({"no-rate-limit"})."""

import pytest
from api.logic_rate_limit import LimitResult, assess, probe_login_limit
from sandpay_vuln import LOGIN_LIMIT, make_app, serve

pytestmark = pytest.mark.exercise


def test_vulnerable_portal_is_never_limited():
    with serve(make_app()) as base:
        result = probe_login_limit(base)
    assert isinstance(result, LimitResult)
    assert result.statuses == [401] * (LOGIN_LIMIT + 3)
    assert result.first_429_at is None and result.retry_after is None and not result.limited
    assert result.other_account_status == 401
    assert assess(result) == "no-rate-limit"


def test_fixed_portal_limits_after_the_documented_number_of_attempts():
    with serve(make_app({"no-rate-limit"})) as base:
        result = probe_login_limit(base)
    assert result.statuses == [401] * LOGIN_LIMIT + [429] * 3
    assert result.first_429_at == LOGIN_LIMIT + 1
    assert result.retry_after == 60
    assert result.limited
    assert assess(result) is None  # no false positive


def test_the_limit_is_per_account_so_another_account_is_not_locked_out():
    with serve(make_app({"no-rate-limit"})) as base:
        result = probe_login_limit(base)
    assert result.other_account_status == 401


def test_assess_flags_a_limit_that_also_blocks_other_accounts():
    shared = LimitResult([401] * 5 + [429], 6, 60, 429)
    assert assess(shared) == "shared-lockout"


def test_assess_needs_nothing_but_the_result():
    assert assess(LimitResult([401, 401], None, None, 401)) == "no-rate-limit"
    assert assess(LimitResult([401, 429], 2, None, 401)) is None


def test_too_few_attempts_is_refused():
    with serve(make_app()) as base:
        with pytest.raises(ValueError):
            probe_login_limit(base, attempts=1)


def test_a_failed_control_raises_instead_of_giving_a_verdict(monkeypatch):
    import api.logic_rate_limit as module

    class Fake:
        status_code = 200
        headers = {}

    monkeypatch.setattr(module.requests, "post", lambda *a, **k: Fake())
    with pytest.raises(RuntimeError):
        probe_login_limit("http://127.0.0.1:9")
