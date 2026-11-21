"""Checks exercises/capstone/pcap_plan.py - the plan the capstone's load follows."""

import pytest
from capstone.pcap_plan import ceiling_rps, engagement_plan, mean_service_ms, run_seconds, transaction_rates
from pcap_fixture import BASE_SERVICE_MS, MIX, SERVICE_FACTOR, WORKERS

pytestmark = pytest.mark.exercise

SERVICE_MS = {tx: BASE_SERVICE_MS * f for tx, f in SERVICE_FACTOR.items()}


def test_rates_split_the_total_by_weight():
    rates = transaction_rates(MIX, 60)
    assert rates == pytest.approx({"POST /v1/payments": 24, "GET /v1/payments": 18, "GET /v1/payments/{id}": 15,
                                   "GET /v1/reports/settlement": 3})
    assert sum(rates.values()) == pytest.approx(60)


def test_mean_service_time_is_weighted_by_the_mix_not_a_plain_average():
    plain = sum(SERVICE_MS.values()) / len(SERVICE_MS)
    assert plain == pytest.approx(70.0)
    assert mean_service_ms(MIX, SERVICE_MS) == pytest.approx(37.0)


def test_ceiling_is_workers_over_mean_service_time():
    assert ceiling_rps(8, 37.0) == pytest.approx(216.2, abs=0.05)
    assert ceiling_rps(1, 100) == pytest.approx(10)


@pytest.mark.parametrize("rate, samples, warmup, expected", [(3, 100, 5, 39), (3, 100, 0, 34), (10, 100, 5, 15),
                                                           (0.5, 50, 10, 110)])
def test_run_seconds_covers_the_samples_after_the_warm_up(rate, samples, warmup, expected):
    assert run_seconds(rate, samples, warmup) == expected


def test_default_warm_up_is_five_seconds():
    assert run_seconds(4, 100) == 30


def test_the_engagement_plan_at_60_requests_per_second():
    plan = engagement_plan(MIX, SERVICE_MS, WORKERS, 60, think_s=0.3)
    assert plan["rates"]["GET /v1/reports/settlement"] == pytest.approx(3)
    assert plan["mean_service_ms"] == pytest.approx(37.0)
    assert plan["ceiling_rps"] == pytest.approx(216.2, abs=0.05)
    assert plan["utilisation"] == 0.28
    assert plan["users"] == 21
    assert plan["rarest"] == "GET /v1/reports/settlement"
    assert plan["run_seconds"] == 39
    assert plan["warnings"] == [] and plan["ok"] is True


def test_a_target_close_to_the_ceiling_gets_a_warning():
    plan = engagement_plan(MIX, SERVICE_MS, WORKERS, 180, think_s=0.3)
    assert plan["utilisation"] == 0.83
    assert plan["ok"] is False
    assert len(plan["warnings"]) == 1 and plan["warnings"][0].startswith("utilisation ")


def test_the_warning_threshold_is_a_parameter():
    assert engagement_plan(MIX, SERVICE_MS, WORKERS, 180, 0.3, max_utilisation=0.9)["ok"] is True


def test_more_think_time_needs_more_users_for_the_same_rate():
    quick = engagement_plan(MIX, SERVICE_MS, WORKERS, 60, think_s=0.1)["users"]
    slow = engagement_plan(MIX, SERVICE_MS, WORKERS, 60, think_s=1.0)["users"]
    assert quick == 9 and slow == 63


@pytest.mark.parametrize("call", [
    lambda: transaction_rates({}, 10),
    lambda: transaction_rates({"a": 1, "b": 0}, 10),
    lambda: transaction_rates({"a": 1}, 0),
    lambda: mean_service_ms({"a": 1, "b": 1}, {"a": 10}),
    lambda: ceiling_rps(0, 10),
    lambda: ceiling_rps(4, 0),
    lambda: run_seconds(0, 100),
    lambda: engagement_plan({}, {}, 8, 60, 0.3),
])
def test_bad_input_is_rejected(call):
    with pytest.raises(ValueError):
        call()
