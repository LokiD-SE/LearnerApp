import pytest

pytestmark = pytest.mark.exercise

from analysis.bn_use import limiting, saturation, use_findings, utilization  # noqa: E402
from bn_fixture import Sampler, run_level, serve_separately  # noqa: E402


def test_utilization_is_busy_workers_over_capacity():
    samples = [{"in_flight": 4, "waiting": 3}, {"in_flight": 3, "waiting": 0}, {"in_flight": 2, "waiting": 0}]
    assert utilization(samples, 4) == 0.75
    assert utilization([], 4) == 0.0


def test_saturation_is_the_mean_queue_length():
    samples = [{"in_flight": 4, "waiting": 3}, {"in_flight": 4, "waiting": 0}, {"in_flight": 4, "waiting": 1}]
    assert saturation(samples) == 1.33
    assert saturation([]) == 0.0


def test_findings_come_in_the_use_order_errors_first():
    assert use_findings(0.30, 0, 0) == []
    assert use_findings(0.95, 0, 0) == ["high-utilization"]
    assert use_findings(0.95, 2.5, 0) == ["saturated", "high-utilization"]
    assert use_findings(0.40, 0, 3) == ["errors"]
    assert use_findings(1.0, 4, 7) == ["errors", "saturated", "high-utilization"]


def test_a_queue_under_half_a_request_is_sampling_noise():
    assert use_findings(0.40, 0.07, 0) == []
    assert use_findings(0.40, 0.49, 0) == []
    assert use_findings(0.40, 0.5, 0) == ["saturated"]


def test_seventy_percent_is_the_line():
    assert use_findings(0.69, 0, 0) == []
    assert use_findings(0.70, 0, 0) == ["high-utilization"]


def test_the_longest_queue_names_the_bottleneck():
    resources = {
        "web workers": {"utilization": 0.35, "saturation": 0, "errors": 0},
        "app threads": {"utilization": 0.82, "saturation": 0, "errors": 0},
        "db connections": {"utilization": 1.0, "saturation": 11.5, "errors": 0},
    }
    assert limiting(resources) == "db connections"


def test_without_a_queue_the_busiest_resource_is_named():
    resources = {
        "cpu": {"utilization": 0.72, "saturation": 0, "errors": 0},
        "disk": {"utilization": 0.91, "saturation": 0, "errors": 0},
    }
    assert limiting(resources) == "disk"


def test_errors_alone_are_not_a_bottleneck_and_idle_means_none():
    resources = {
        "cache": {"utilization": 0.10, "saturation": 0, "errors": 12},
        "pool": {"utilization": 0.40, "saturation": 0, "errors": 0},
    }
    assert limiting(resources) is None
    assert limiting({}) is None


def test_ties_go_to_utilization_then_to_the_name():
    resources = {
        "b": {"utilization": 1.0, "saturation": 2, "errors": 0},
        "a": {"utilization": 1.0, "saturation": 2, "errors": 0},
    }
    assert limiting(resources) == "a"
    resources["b"]["utilization"] = 1.0
    resources["a"]["utilization"] = 0.9
    assert limiting(resources) == "b"


def _read(base_url, capacity, clients, requests_each=20, **kw):
    with Sampler(base_url) as sampler:
        result = run_level(base_url, clients, requests_each, **kw)
    util, sat = utilization(sampler.samples, capacity), saturation(sampler.samples)
    return use_findings(util, sat, result["errors"]), util, sat


def test_against_the_real_target_a_light_load_is_clear_and_a_heavy_load_is_saturated():
    with serve_separately(latency_ms=20, capacity=4) as url:
        light, light_util, _ = _read(url, 4, clients=2)
        heavy, heavy_util, heavy_sat = _read(url, 4, clients=16)
    assert light == [] and light_util < 0.7
    assert "saturated" in heavy and "high-utilization" in heavy
    assert heavy_util > 0.8 and heavy_sat > 3


def test_a_slow_load_generator_does_not_make_the_target_a_bottleneck():
    # 16 clients, each burning 30 ms of CPU between requests: the generator is the limit, the target is idle.
    with serve_separately(latency_ms=20, capacity=4) as url:
        findings, util, sat = _read(url, 4, clients=16, requests_each=6, burn_ms=30)
    assert findings == []
    assert util < 0.7 and sat < 0.5


def test_a_full_queue_shows_up_as_errors():
    with serve_separately(latency_ms=20, capacity=4, queue_limit=4) as url:
        findings, _, _ = _read(url, 4, clients=24, requests_each=15)
    assert "errors" in findings
