"""Exercise: timer scope and pauses (jmeter/jm_threads_timers.py). One test checks the model against real JMeter."""

import statistics
from pathlib import Path

import pytest
from jmeter.jm_threads_timers import (
    delay_bounds_ms,
    expected_delay_ms,
    iteration_ms,
    samplers,
    throughput_per_minute,
    timers_in_scope,
)
from load_tools import jmeter_home, read_jtl, run_jmeter
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

FIXTURES = Path(__file__).parent / "fixtures"


def const(name, ms):
    return {"type": "ConstantTimer", "name": name, "delay_ms": ms}


def uniform(name, offset, rng):
    return {"type": "UniformRandomTimer", "name": name, "offset_ms": offset, "range_ms": rng}


def gauss(name, offset, dev):
    return {"type": "GaussianRandomTimer", "name": name, "offset_ms": offset, "deviation_ms": dev}


def sampler(name, *children):
    return {"type": "Sampler", "name": name, "children": list(children)}


# A checkout journey: a group-wide think time, a timer that only the payment sampler gets, a controller whose
# timer covers both samplers under it - and that timer sits AFTER the samplers in the tree.
PLAN = {
    "type": "ThreadGroup",
    "name": "Merchants",
    "children": [
        const("think", 300),
        sampler("GET /v1/payments"),
        {
            "type": "Controller",
            "name": "Checkout",
            "children": [
                sampler("POST /auth/token"),
                sampler("POST /v1/payments", const("pay pause", 200)),
                uniform("checkout jitter", 100, 400),
            ],
        },
        {"type": "Controller", "name": "Reports", "children": [sampler("GET /v1/reports/settlement"), gauss("g", 1000, 250)]},
    ],
}


def names(timers):
    return sorted(t["name"] for t in timers)


def test_group_level_timer_applies_to_every_sampler():
    for s in samplers(PLAN):
        assert "think" in names(timers_in_scope(PLAN, s))


def test_timer_under_a_sampler_applies_only_to_it():
    assert names(timers_in_scope(PLAN, "POST /v1/payments")) == ["checkout jitter", "pay pause", "think"]
    assert names(timers_in_scope(PLAN, "POST /auth/token")) == ["checkout jitter", "think"]


def test_position_among_siblings_does_not_matter_but_scope_does():
    # "checkout jitter" comes after the samplers in the tree and still applies to them;
    # the Reports controller's timer never reaches samplers outside Reports.
    assert names(timers_in_scope(PLAN, "GET /v1/payments")) == ["think"]
    assert "g" in names(timers_in_scope(PLAN, "GET /v1/reports/settlement"))


def test_unknown_sampler():
    with pytest.raises(KeyError):
        timers_in_scope(PLAN, "DELETE /v1/payments")


def test_expected_delay_is_the_sum_of_the_means():
    assert expected_delay_ms(PLAN, "GET /v1/payments") == 300
    assert expected_delay_ms(PLAN, "POST /auth/token") == 300 + 100 + 200  # uniform mean: offset + range / 2
    assert expected_delay_ms(PLAN, "POST /v1/payments") == 300 + 200 + 300
    assert expected_delay_ms(PLAN, "GET /v1/reports/settlement") == 300 + 1000  # Gaussian mean is its offset


def test_bounds():
    assert delay_bounds_ms(PLAN, "POST /v1/payments") == (600, 1000)
    assert delay_bounds_ms(PLAN, "GET /v1/payments") == (300, 300)
    assert delay_bounds_ms(PLAN, "GET /v1/reports/settlement") is None


def test_samplers_in_tree_order():
    assert samplers(PLAN) == ["GET /v1/payments", "POST /auth/token", "POST /v1/payments", "GET /v1/reports/settlement"]


def test_iteration_time_and_throughput():
    response = {"GET /v1/payments": 50, "POST /auth/token": 40, "POST /v1/payments": 110, "GET /v1/reports/settlement": 200}
    # delays 300 + 600 + 800 + 1300 = 3000 ms; responses 400 ms
    assert iteration_ms(PLAN, response) == 3400
    # 10 threads x 4 samples per 3.4 s iteration
    assert throughput_per_minute(PLAN, response, threads=10) == pytest.approx(10 * 4 * 60_000 / 3400)


@pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")
def test_model_matches_real_jmeter(tmp_path):
    # fixtures/jm_threads_two_timers.jmx: one thread, a Constant Timer (100 ms) and a Uniform Random Timer
    # (offset 150 ms, range 0) side by side in the Thread Group, one sampler.
    model = {"type": "ThreadGroup", "name": "Merchants",
             "children": [sampler("GET /health"), const("Think time 100 ms", 100), uniform("Uniform", 150, 0)]}
    expected = expected_delay_ms(model, "GET /health")
    assert expected == 250
    with serve(TargetConfig(latency_ms=1)) as base:
        jtl = run_jmeter(FIXTURES / "jm_threads_two_timers.jmx", {"port": base.rsplit(":", 1)[1], "loops": 6}, tmp_path)
    data = read_jtl(jtl)
    starts = [int(r["timeStamp"]) for r in data]
    elapsed = [int(r["elapsed"]) for r in data]
    pauses = [starts[i + 1] - starts[i] - elapsed[i] for i in range(len(data) - 1)]
    assert min(pauses) >= expected - 5, pauses
    assert statistics.median(pauses) <= expected + 40, pauses
