import pytest
from fundamentals.little_calc import (
    concurrency,
    locust_constant_throughput,
    max_closed_throughput,
    pacing_seconds,
    response_time_from,
    users_needed,
)

pytestmark = pytest.mark.exercise


def test_concurrency_is_throughput_times_residence():
    # 200 requests/s that each spend 0.05 s in the system: 10 in the system on average
    assert concurrency(200, 0.05) == pytest.approx(10)
    assert concurrency(0, 3) == 0


def test_concurrency_rejects_negative_inputs():
    with pytest.raises(ValueError):
        concurrency(-1, 0.1)
    with pytest.raises(ValueError):
        concurrency(10, -0.1)


def test_users_needed_without_think_time():
    # 100 requests/s at 0.25 s each: 25 requests always in flight, so 25 users
    assert users_needed(100, 0.25) == 25


def test_users_needed_with_think_time_qsp_example():
    # QSP chapter 3: 10 users, think time 5 s, response time 15 s give 0.5 interactions/s - and back again
    assert users_needed(0.5, 15, 5) == 10


def test_users_needed_rounds_up():
    # 30 requests/s * (0.2 + 1.0) s = 36 exactly; 31/s needs 37.2 -> 38 users
    assert users_needed(30, 0.2, 1.0) == 36
    assert users_needed(31, 0.2, 1.0) == 38


def test_users_needed_with_several_requests_per_iteration():
    # 3 requests of 0.1 s each, then 2.7 s think time: 3 s per iteration; 60 requests/s = 20 iterations/s
    assert users_needed(60, 0.1, 2.7, requests_per_iteration=3) == 60


def test_users_needed_validates():
    with pytest.raises(ValueError):
        users_needed(10, 0.1, requests_per_iteration=0)
    with pytest.raises(ValueError):
        users_needed(-10, 0.1)


def test_response_time_law_qsp_example():
    # QSP chapter 3: 64 users, think time 30 s, throughput 2/s -> response time 2 s
    assert response_time_from(64, 2, 30) == pytest.approx(2)


def test_response_time_law_flags_inconsistent_measurements():
    with pytest.raises(ValueError, match="inconsistent"):
        response_time_from(10, 5, 3)  # 10/5 - 3 = -1 s
    with pytest.raises(ValueError):
        response_time_from(10, 0, 1)


def test_pacing_and_locust_argument():
    assert pacing_seconds(20, 5) == pytest.approx(0.25)
    assert locust_constant_throughput(20, 5) == pytest.approx(4)
    # two requests per task: each user runs its task half as often
    assert locust_constant_throughput(20, 5, requests_per_iteration=2) == pytest.approx(2)
    with pytest.raises(ValueError):
        pacing_seconds(0, 5)


def test_max_closed_throughput_is_capped_by_the_slower_of_pacing_and_iteration():
    assert max_closed_throughput(5, 0.05, pacing_s=0.25) == pytest.approx(20)   # pacing rules
    assert max_closed_throughput(5, 0.5, pacing_s=0.25) == pytest.approx(10)    # the server rules
    assert max_closed_throughput(10, 0.5) == pytest.approx(20)
    assert max_closed_throughput(4, 1.0, requests_per_iteration=3) == pytest.approx(12)
    with pytest.raises(ValueError):
        max_closed_throughput(5, 0, 0)
