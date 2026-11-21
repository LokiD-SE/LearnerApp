"""Checks exercises/analysis/tc_sizing.py: what a load generator costs and how many you need.

Hand-made runs with the arithmetic worked out in comments, then the captured runs of the lesson
(support/tc_data/runs.json: JMeter 5.6.3 and Locust 2.47.0 on one machine, 21 November 2026)."""

import pytest
import tc_fixture as fx
from analysis.tc_sizing import (cheapest, cores_busy, cpu_per_1000, cpu_seconds, generators_needed, marginal_cpu_per_1000,
                                mb_per_user, median_of)

pytestmark = pytest.mark.exercise

RUN = {"users": 10, "requests": 2000, "wall_s": 10.0, "cpu_user_s": 3.0, "cpu_sys_s": 1.0, "rss_peak_mb": 100.0}
STARTUP = {"users": 1, "requests": 20, "wall_s": 2.0, "cpu_user_s": 1.5, "cpu_sys_s": 0.5, "rss_peak_mb": 80.0}
BIG = {"users": 510, "requests": 2000, "wall_s": 10.0, "cpu_user_s": 3.0, "cpu_sys_s": 1.0, "rss_peak_mb": 120.0}


def test_cpu_seconds_is_user_plus_system():
    assert cpu_seconds(RUN) == 4.0


def test_cores_busy_can_be_above_one():
    assert cores_busy(RUN) == 0.4  # 4 CPU seconds in 10 wall seconds
    assert cores_busy({**RUN, "cpu_user_s": 19.0, "cpu_sys_s": 1.0}) == 2.0  # a multi-threaded tool


def test_cpu_per_1000_includes_the_fixed_cost():
    assert cpu_per_1000(RUN) == 2.0  # 4 CPU s over 2000 requests, per 1000
    assert cpu_per_1000(STARTUP) == pytest.approx(100.0)  # 2 CPU s over 20 requests: almost all start-up


def test_marginal_cost_takes_the_start_up_out():
    # (4 - 2) CPU s over (2000 - 20) requests, per 1000
    assert marginal_cpu_per_1000(RUN, STARTUP) == pytest.approx(2 / 1980 * 1000)
    assert marginal_cpu_per_1000(RUN, STARTUP) < cpu_per_1000(RUN)


def test_memory_per_user_is_a_slope_not_a_total():
    assert mb_per_user(RUN, BIG) == pytest.approx(20 / 500)  # 20 MB more for 500 more users
    assert mb_per_user(STARTUP, RUN) == pytest.approx(20 / 9)


def test_median_of_takes_a_key_or_a_function():
    runs = [{"cpu_user_s": 1.0, "cpu_sys_s": 0.5}, {"cpu_user_s": 9.0, "cpu_sys_s": 1.0}, {"cpu_user_s": 2.0, "cpu_sys_s": 0.0}]
    assert median_of(runs, "cpu_user_s") == 2.0
    assert median_of(runs, cpu_seconds) == 2.0  # 1.5, 10.0 and 2.0
    assert median_of(runs[:2], "cpu_user_s") == 5.0  # the median of two is their mean


def test_generators_needed_rounds_up_and_keeps_headroom():
    assert generators_needed(1000, 500) == 3  # 1000 / (500 x 0.7) = 2.86
    assert generators_needed(1000, 500, max_busy=1.0) == 2
    assert generators_needed(1400, 1000) == 2  # exactly 1400 / 700 = 2 - no extra generator
    assert generators_needed(1, 1000) == 1
    assert generators_needed(0, 1000) == 1  # never zero generators


def test_cheapest_picks_by_median_and_breaks_ties_by_name():
    setups = {
        "b": [{"cpu_user_s": 5.0, "cpu_sys_s": 0.0}, {"cpu_user_s": 1.0, "cpu_sys_s": 0.0}, {"cpu_user_s": 6.0, "cpu_sys_s": 0.0}],
        "a": [{"cpu_user_s": 4.0, "cpu_sys_s": 0.0}, {"cpu_user_s": 4.0, "cpu_sys_s": 0.0}, {"cpu_user_s": 9.0, "cpu_sys_s": 0.0}],
        "c": [{"cpu_user_s": 4.0, "cpu_sys_s": 0.0}] * 3,
    }
    assert cheapest(setups, "cpu_user_s") == "a"  # medians: b 5.0, a 4.0, c 4.0 - a and c tie, a sorts first
    assert cheapest(setups, cpu_seconds) == "a"


def runs(scenario, setup):
    return [r for r in fx.captured()["runs"] if r["scenario"] == scenario and r["setup"] == setup]


def typical(rs, key):
    """The repeat whose ``key`` is the middle one of three."""
    return sorted(rs, key=key if callable(key) else lambda r: r[key])[len(rs) // 2]


def test_captured_start_up_cost_of_the_jvm_is_many_times_locusts():
    jmeter = median_of(runs("startup", "jmeter-default"), cpu_seconds)
    locust = median_of(runs("startup", "locust-http"), cpu_seconds)
    assert jmeter > 5 * locust  # 7.19 and 0.86 CPU seconds when captured: a one-second test costs seven in JMeter
    assert cores_busy(typical(runs("startup", "jmeter-default"), cpu_seconds)) > 1  # more CPU seconds than wall seconds


def test_captured_cost_per_request_after_start_up():
    startup = {su: typical(runs("startup", su), cpu_seconds) for su in ("jmeter-default", "locust-http", "locust-fast")}
    steady = {su: typical(runs("steady", su), cpu_seconds) for su in startup}
    marginal = {su: marginal_cpu_per_1000(steady[su], startup[su]) for su in startup}
    assert marginal["locust-fast"] < marginal["locust-http"] < marginal["jmeter-default"]
    assert marginal["locust-fast"] * 2 < marginal["locust-http"]  # FastHttpUser costs well under half of HttpUser
    assert all(0 < v < cpu_per_1000(steady[su]) for su, v in marginal.items())  # the fixed cost is always taken out


def test_captured_memory_grows_far_faster_per_user_in_jmeter():
    slope = {su: mb_per_user(typical(runs("steady", su), "rss_peak_mb"), typical(runs("many", su), "rss_peak_mb"))
             for su in ("jmeter-default", "locust-http")}
    assert slope["locust-http"] > 0
    assert slope["jmeter-default"] > 4 * slope["locust-http"]  # about 0.3 MB and 0.04 MB per user when captured


def test_captured_sizing_needs_more_jmeter_cores_than_fastest_locust():
    def per_core(su):
        s0, s1 = (typical(runs(sc, su), cpu_seconds) for sc in ("startup", "steady"))
        return 1000 / marginal_cpu_per_1000(s1, s0)

    assert generators_needed(2000, per_core("jmeter-default")) > generators_needed(2000, per_core("locust-fast"))
    assert cheapest({su: runs("steady", su) for su in ("jmeter-default", "locust-http", "locust-fast")}, cpu_per_1000) == "locust-fast"
