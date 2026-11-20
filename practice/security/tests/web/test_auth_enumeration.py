"""Checks practice/security/exercises/web/auth_enumeration.py (testing-authentication lesson)."""

import pytest
from auth_fixture import serve_login
from sandpay_vuln import FLAWS, make_app, serve
from web.auth_enumeration import Observation, check_enumeration, compare

pytestmark = pytest.mark.exercise

KNOWN, UNKNOWN = "alice@shop-a.example", "nobody@shop-a.example"
BODY = '{"error": "invalid email or password"}'


def obs(status=401, body=BODY, ms=2.0, n=4):
    return [Observation(status, body, ms)] * n


def test_compare_finds_nothing_when_responses_match():
    assert compare(obs(ms=2.0), obs(ms=1.5)) == {"enumerable": False, "signals": [], "known_median_ms": 2.0,
                                               "unknown_median_ms": 1.5}


def test_compare_names_each_signal():
    assert compare(obs(status=401), obs(status=404))["signals"] == ["status"]
    assert compare(obs(body="wrong password"), obs(body="no account"))["signals"] == ["message"]
    assert compare(obs(ms=118.0), obs(ms=0.8))["signals"] == ["timing"]
    assert compare(obs(ms=0.8), obs(ms=118.0))["signals"] == ["timing"], "a gap in either direction counts"


def test_compare_ignores_small_or_relative_only_gaps():
    assert compare(obs(ms=6.0), obs(ms=1.0))["signals"] == []  # 6x, but only 5 ms apart
    assert compare(obs(ms=330.0), obs(ms=300.0))["signals"] == []  # 30 ms apart, but only 1.1x


def test_compare_uses_medians_not_means():
    known = [Observation(401, BODY, ms) for ms in (1.0, 1.2, 1.1, 400.0)]  # one slow outlier
    assert compare(known, obs(ms=1.0))["signals"] == []


def test_compare_needs_observations():
    with pytest.raises(ValueError):
        compare([], obs())


@pytest.mark.parametrize("variant, signals", [
    ("uniform", []), ("message", ["message"]), ("status", ["status"]), ("timing", ["timing"]),
])
def test_finds_exactly_the_leaking_signal(variant, signals):
    with serve_login(variant) as base:
        result = check_enumeration(base, KNOWN, UNKNOWN, samples=3, path="/login")
    assert result["signals"] == signals, result
    assert result["enumerable"] is bool(signals) and result["rate_limited"] is False


def test_md5_portal_does_not_leak():
    with serve(make_app()) as base:
        result = check_enumeration(base, KNOWN, UNKNOWN)
    assert result["enumerable"] is False, result


def test_fixing_weak_hash_opens_a_timing_oracle():
    # PBKDF2 runs only when the email exists - the "quick exit" the OWASP cheat sheet warns about
    with serve(make_app(FLAWS)) as base:
        result = check_enumeration(base, KNOWN, UNKNOWN)
    assert result["signals"] == ["timing"], result
    assert result["known_median_ms"] > result["unknown_median_ms"]


def test_a_429_makes_the_result_inconclusive():
    with serve(make_app({"no-rate-limit"})) as base:
        result = check_enumeration(base, KNOWN, UNKNOWN, samples=8)  # 8 tries for one email > limit of 5
    assert result["enumerable"] is None and result["rate_limited"] is True


def test_refuses_other_hosts():
    with pytest.raises(ValueError):
        check_enumeration("http://portal.sandpay.example", KNOWN, UNKNOWN)
