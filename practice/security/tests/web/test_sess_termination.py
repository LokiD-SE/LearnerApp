"""Checks exercises/web/sess_termination.py. The service's clock is fake: ``app.clock.advance`` stands in for
waiting, so hours of session lifetime take milliseconds and every run gives the same answer."""

import pytest
from sess_fixture import ABSOLUTE_TIMEOUT_S, IDLE_TIMEOUT_S, make_app, serve
from web.sess_termination import is_valid, sign_in, verify_logout, verify_timeouts

pytestmark = pytest.mark.exercise

ALICE = ("alice@shop-a.example", "alice-pass-1")


def test_client_only_logout_is_found():
    with serve(make_app()) as base:
        r = verify_logout(base, *ALICE)
    assert r.cookie_cleared is True  # the browser is told to forget the cookie ...
    assert r.old_id_rejected is False and r.vulnerable is True  # ... but the server still accepts it


def test_server_side_logout_passes():
    with serve(make_app({"logout-client-only"})) as base:
        r = verify_logout(base, *ALICE)
    assert (r.cookie_cleared, r.old_id_rejected, r.vulnerable) == (True, True, False)


def run_timeouts(fixed):
    app = make_app(fixed)
    with serve(app) as base:
        return verify_timeouts(base, *ALICE, wait=app.clock.advance, idle_limit_s=IDLE_TIMEOUT_S,
                               absolute_limit_s=ABSOLUTE_TIMEOUT_S)


def test_missing_timeouts_are_found():
    r = run_timeouts(set())
    assert r.idle_enforced is False and r.absolute_enforced is False
    assert r.observed_lifetime_s >= ABSOLUTE_TIMEOUT_S  # report what was seen: alive for the whole window


def test_idle_timeout_only():
    r = run_timeouts({"no-idle-timeout"})
    assert r.idle_enforced is True and r.absolute_enforced is False


def test_absolute_timeout_only():
    # The busy session must not be ended by the idle rule (it is not enforced here) - only the absolute one.
    r = run_timeouts({"no-absolute-timeout"})
    assert r.idle_enforced is False and r.absolute_enforced is True
    assert ABSOLUTE_TIMEOUT_S <= r.observed_lifetime_s <= ABSOLUTE_TIMEOUT_S + IDLE_TIMEOUT_S


def test_both_timeouts_enforced():
    r = run_timeouts({"no-idle-timeout", "no-absolute-timeout"})
    assert r.idle_enforced is True and r.absolute_enforced is True
    # Kept busy every half idle-limit, so only the absolute limit can have ended it.
    assert ABSOLUTE_TIMEOUT_S <= r.observed_lifetime_s <= ABSOLUTE_TIMEOUT_S + IDLE_TIMEOUT_S


def test_helpers():
    with serve(make_app()) as base:
        sid = sign_in(base, *ALICE)
        assert is_valid(base, sid) and not is_valid(base, "s-not-issued")
        with pytest.raises(RuntimeError):
            sign_in(base, "alice@shop-a.example", "nope")
