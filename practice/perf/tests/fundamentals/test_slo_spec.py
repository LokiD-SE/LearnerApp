import pytest
from fundamentals.slo_spec import Requirement, UntestableRequirement, parse_requirement, review

pytestmark = pytest.mark.exercise


def reasons(text):
    with pytest.raises(UntestableRequirement) as e:
        parse_requirement(text)
    return set(e.value.reasons)


def test_percentile_form():
    r = parse_requirement("p95 of POST /v1/payments < 300 ms at 50 req/s")
    assert r == Requirement("latency", "POST /v1/payments", 50.0, "req/s", percentile=95.0, threshold_ms=300.0)


def test_sre_style_form_and_seconds():
    r = parse_requirement("99% of GET /v1/payments complete in under 0.2 s at 40 req/s")
    assert (r.kind, r.transaction, r.percentile, r.threshold_ms, r.load) == ("latency", "GET /v1/payments", 99.0, 200.0, 40.0)


def test_users_load_and_path_parameter():
    r = parse_requirement("p99 of GET /v1/payments/{id} <= 250 ms at 200 concurrent users")
    assert (r.transaction, r.load, r.load_unit, r.threshold_ms) == ("GET /v1/payments/{id}", 200.0, "users", 250.0)


def test_error_rate_form():
    r = parse_requirement("error rate of POST /v1/payments below 0.5% at 50 req/s")
    assert (r.kind, r.max_error_percent, r.percentile, r.threshold_ms) == ("errors", 0.5, None, None)


def test_vague_requirement_gets_every_reason():
    assert reasons("The payments page must be fast") == {"no-transaction", "no-threshold", "no-load"}


def test_average_is_rejected():
    assert reasons("Average response time of GET /v1/payments under 200 ms at 40 req/s") == {"average"}


def test_missing_load():
    assert reasons("p95 of POST /v1/payments < 300 ms") == {"no-load"}


def test_absolute_targets():
    assert reasons("100% of GET /health complete within 50 ms at 10 req/s") == {"absolute"}
    assert "absolute" in reasons("GET /v1/payments must always respond within 100 ms at 10 req/s")


def test_missing_percentile():
    assert reasons("POST /v1/payments < 300 ms at 50 req/s") == {"no-percentile"}


def test_error_rate_without_number():
    assert reasons("error rate of POST /v1/payments must be low at 50 req/s") == {"no-threshold"}


def test_review_maps_each_text():
    out = review(["p95 of POST /v1/payments < 300 ms at 50 req/s", "it should scale"])
    assert isinstance(out["p95 of POST /v1/payments < 300 ms at 50 req/s"], Requirement)
    assert set(out["it should scale"]) == {"no-transaction", "no-threshold", "no-load"}
