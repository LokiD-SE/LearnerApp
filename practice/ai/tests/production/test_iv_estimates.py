import pytest
from production.iv_estimates import (
    Prices,
    Workload,
    concurrency,
    cost_per_request,
    daily_cost,
    max_requests_within_budget,
    response_seconds,
)

pytestmark = pytest.mark.exercise

# Assumed prices for practice, EUR per million tokens - not any provider's price list.
PRICES = Prices(input=3.0, output=15.0, cached_input=0.3)
SUPPORT = Workload(requests_per_day=40_000, input_tokens=6_000, output_tokens=400)


def test_cost_per_request_without_cache():
    # 6000 x 3 + 400 x 15 = 24 000 per million -> 0.024
    assert cost_per_request(SUPPORT, PRICES) == pytest.approx(0.024)


def test_daily_cost_without_cache():
    assert daily_cost(SUPPORT, PRICES) == pytest.approx(960.0)


def test_cached_tokens_are_priced_separately():
    cached = Workload(40_000, 6_000, 400, cached_input_tokens=4_000)
    # 2000 x 3 + 4000 x 0.3 + 400 x 15 = 13 200 per million
    assert cost_per_request(cached, PRICES) == pytest.approx(0.0132)
    assert daily_cost(cached, PRICES) == pytest.approx(528.0)


def test_daily_cost_rounds_to_cents():
    w = Workload(requests_per_day=7, input_tokens=1_001, output_tokens=0)
    assert daily_cost(w, PRICES) == 0.02  # 7 x 0.003003 = 0.021021


def test_output_tokens_dominate_when_replies_are_long():
    short_prompt_long_reply = Workload(1, 500, 2_000)
    assert cost_per_request(short_prompt_long_reply, PRICES) == pytest.approx(0.0315)


def test_cached_cannot_exceed_input():
    with pytest.raises(ValueError):
        cost_per_request(Workload(1, 100, 10, cached_input_tokens=101), PRICES)


def test_negative_counts_are_rejected():
    with pytest.raises(ValueError):
        daily_cost(Workload(-1, 100, 10), PRICES)


def test_response_seconds():
    assert response_seconds(0.8, 400, 50) == pytest.approx(8.8)
    assert response_seconds(0.5, 0, 50) == pytest.approx(0.5)


def test_response_seconds_rejects_zero_speed():
    with pytest.raises(ValueError):
        response_seconds(0.5, 10, 0)


def test_concurrency_uses_littles_law_and_rounds_up():
    # 40 000 / 86 400 x 3 = 1.389 per second; x 8.8 s = 12.2 -> 13 in flight
    assert concurrency(40_000, 3, 8.8) == 13
    assert concurrency(86_400, 1, 2) == 2


def test_concurrency_rejects_peak_below_average():
    with pytest.raises(ValueError):
        concurrency(1000, 0.5, 1)


def test_max_requests_within_budget():
    assert max_requests_within_budget(500.0, SUPPORT, PRICES) == 20_833
    cached = Workload(0, 6_000, 400, cached_input_tokens=4_000)
    assert max_requests_within_budget(500.0, cached, PRICES) == 37_878


def test_free_request_has_no_budget_limit():
    with pytest.raises(ValueError):
        max_requests_within_budget(10.0, Workload(1, 0, 0), PRICES)
