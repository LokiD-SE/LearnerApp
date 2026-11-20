"""Exercise: size a distributed run (jmeter/jm_dist_sizing.py) - threads multiply per server."""

import pytest
from jmeter.jm_dist_sizing import RunSize, size_run, threads_per_server, total_threads

pytestmark = pytest.mark.exercise


def test_the_manuals_example_1000_threads_on_6_servers_is_6000():
    assert total_threads(1000, 6) == 6000


def test_a_local_run_injects_the_plans_threads_once():
    assert total_threads(50, 0) == 50
    assert total_threads(50, 1) == 50


def test_threads_per_server_divides_the_target():
    assert threads_per_server(1000, 4) == 250
    assert threads_per_server(6, 2) == 3


def test_threads_per_server_refuses_to_round_silently():
    with pytest.raises(ValueError):
        threads_per_server(1000, 3)


@pytest.mark.parametrize("args", [(0, 2), (10, 0), (-5, 1)])
def test_threads_per_server_rejects_impossible_counts(args):
    with pytest.raises(ValueError):
        threads_per_server(*args)


def test_total_threads_rejects_negative_counts():
    with pytest.raises(ValueError):
        total_threads(-1, 2)


def test_size_run_examples():
    assert size_run(1000, 300) == RunSize(4, 250, 1000, 0)
    assert size_run(1000, 400) == RunSize(3, 334, 1002, 2)
    assert size_run(800, 2000) == RunSize(1, 800, 800, 0)


def test_size_run_never_exceeds_the_measured_limit_and_always_reaches_the_target():
    for target in range(1, 400, 7):
        for limit in (1, 3, 50, 120, 1000):
            size = size_run(target, limit)
            assert size.threads_per_server <= limit
            assert size.total_threads == size.servers * size.threads_per_server >= target
            assert size.overshoot == size.total_threads - target < size.servers
            fewer = size.servers - 1
            assert fewer == 0 or fewer * limit < target  # no smaller fleet would do


def test_size_run_rejects_impossible_counts():
    with pytest.raises(ValueError):
        size_run(0, 100)
    with pytest.raises(ValueError):
        size_run(100, 0)
