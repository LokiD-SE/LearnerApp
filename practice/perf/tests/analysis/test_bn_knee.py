import pytest

pytestmark = pytest.mark.exercise

from analysis.bn_knee import find_knee, implied_slots, wait_share  # noqa: E402
from bn_fixture import run_steps, serve_separately  # noqa: E402

# A real step load against the practice target (20 ms service time, 4 workers), captured on 21 November 2026.
STEPS = [
    {"clients": 1, "throughput": 46.0, "mean_ms": 21.7},
    {"clients": 2, "throughput": 91.7, "mean_ms": 21.8},
    {"clients": 4, "throughput": 179.3, "mean_ms": 22.3},
    {"clients": 8, "throughput": 191.5, "mean_ms": 40.7},
    {"clients": 16, "throughput": 190.9, "mean_ms": 79.3},
]


def test_the_knee_is_the_last_level_that_still_paid():
    assert find_knee(STEPS) == 4


def test_the_order_of_the_steps_does_not_matter():
    assert find_knee(list(reversed(STEPS))) == 4


def test_a_system_that_never_saturated_has_no_knee():
    below = STEPS[:3]
    assert find_knee(below) is None
    assert find_knee(STEPS[:1]) is None


def test_the_gain_threshold_is_a_parameter():
    # 4 -> 8 clients gained about 7%: a 5% bar still calls that a gain, so the knee moves out to 8.
    assert find_knee(STEPS, min_gain=0.05) == 8
    assert find_knee(STEPS, min_gain=0.99) == 2  # only a near-perfect doubling counts as still paying


def test_wait_share_is_the_part_of_latency_that_is_queueing():
    assert wait_share(STEPS[0], 20) == 0.078
    assert wait_share(STEPS[4], 20) == 0.748
    assert wait_share({"clients": 1, "throughput": 50, "mean_ms": 15.0}, 20) == 0.0


def test_the_ceiling_times_the_service_time_is_the_number_of_slots():
    assert implied_slots(STEPS, 20) == 3.8
    assert implied_slots(STEPS[:3], 20) == 3.6


def test_against_the_real_target_the_knee_sits_at_the_worker_count():
    with serve_separately(latency_ms=20, capacity=4) as url:
        steps = run_steps(url, [1, 2, 4, 8, 16], requests_each=20)
    assert find_knee(steps) in (4, 8)
    assert wait_share(steps[0], 20) < 0.25
    assert wait_share(steps[-1], 20) > 0.5
    assert 3.0 <= implied_slots(steps, 20) <= 4.6
