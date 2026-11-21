"""Checks exercises/devsecops/reg_guard.py: classify a probe as trustworthy, flaky, blind, noisy or broken."""

import pytest
from devsecops.reg_guard import ci_action, classify, run_guard
from reg_fixture import GuardResult, always_false, always_true, broken_control, make_flaky, redirect_probe

pytestmark = pytest.mark.exercise

T, F = True, False


@pytest.mark.parametrize("vulnerable, fixed, verdict", [
    ([T, T, T], [F, F, F], "trustworthy"),
    ([F, F, F], [F, F, F], "blind"),
    ([T, T, T], [T, T, T], "noisy"),
    ([F, F, F], [T, T, T], "noisy"),
    ([T, F, T], [F, F, F], "flaky"),
    ([T, T, T], [F, T, F], "flaky"),
    ([T, F], [T, F], "flaky"),
    ([T], [F], "trustworthy"),
])
def test_classify(vulnerable, fixed, verdict):
    assert classify(vulnerable, fixed) == verdict


def test_classify_accepts_tuples_and_needs_runs_on_both_builds():
    assert classify((T, T), (F, F)) == "trustworthy"
    with pytest.raises(ValueError):
        classify([], [F])
    with pytest.raises(ValueError):
        classify([T], [])


def test_run_guard_calls_a_real_probe_trustworthy():
    result = run_guard(redirect_probe, "open-redirect", runs=3)
    assert isinstance(result, GuardResult)
    assert result == GuardResult("open-redirect", (T, T, T), (F, F, F), "trustworthy")


def test_run_guard_runs_the_probe_the_same_number_of_times_on_each_build():
    calls = []

    def counting(base_url):
        calls.append(base_url)
        return len(calls) <= 4  # True on the 4 vulnerable calls, False on the 4 fixed ones

    result = run_guard(counting, "idor", runs=4)
    assert len(calls) == 8
    assert len(set(calls[:4])) == 1 and len(set(calls[4:])) == 1  # one server per build, not one per run
    assert result.verdict == "trustworthy"


def test_run_guard_calls_the_blind_and_the_noisy_probe_by_name():
    assert run_guard(always_false, "idor", runs=2).verdict == "blind"
    assert run_guard(always_true, "idor", runs=2).verdict == "noisy"


def test_run_guard_catches_a_flaky_probe_with_counter_driven_answers():
    result = run_guard(make_flaky("TTF"), "idor", runs=5)
    assert result.vulnerable_runs == (T, T, F, T, T)
    assert result.fixed_runs == (F, T, T, F, T)
    assert result.verdict == "flaky"


def test_run_guard_reports_a_failed_control_as_broken_and_keeps_what_it_has():
    result = run_guard(broken_control, "idor", runs=3)
    assert result.verdict == "broken"
    assert result.vulnerable_runs == () and result.fixed_runs == ()


def test_run_guard_needs_at_least_one_run():
    with pytest.raises(ValueError):
        run_guard(always_true, "idor", runs=0)


@pytest.mark.parametrize("verdict, days, action", [
    ("trustworthy", 0, "gate"),
    ("trustworthy", 99, "gate"),
    ("flaky", 0, "quarantine"),
    ("flaky", 14, "quarantine"),
    ("flaky", 15, "escalate"),
    ("blind", 0, "fix-test"),
    ("noisy", 0, "fix-test"),
    ("broken", 0, "fix-test"),
])
def test_ci_action(verdict, days, action):
    assert ci_action(verdict, days) == action


def test_ci_action_honours_max_days_and_never_turns_the_unknown_into_a_pass():
    assert ci_action("flaky", 7, max_days=7) == "quarantine"
    assert ci_action("flaky", 8, max_days=7) == "escalate"
    with pytest.raises(ValueError):
        ci_action("passed")
    with pytest.raises(ValueError):
        ci_action("")
