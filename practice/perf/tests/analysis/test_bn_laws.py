import pytest

pytestmark = pytest.mark.exercise

from analysis.bn_laws import (  # noqa: E402
    bottleneck,
    demand,
    knee_population,
    max_throughput,
    throughput_bounds,
    what_if,
)

# Hypothetical request path (made-up numbers, in seconds per request).
PATH = {"web": 0.004, "app": 0.012, "db": 0.025}


def test_demand_law():
    assert demand(0.5, 20) == pytest.approx(0.025)
    assert demand(1.0, 200) == pytest.approx(0.005)


def test_the_largest_demand_is_the_bottleneck_and_sets_the_ceiling():
    assert bottleneck(PATH) == "db"
    assert max_throughput(PATH) == pytest.approx(40.0)


def test_a_tie_goes_to_the_first_name():
    assert bottleneck({"b": 0.01, "a": 0.01, "c": 0.002}) == "a"


def test_knee_population():
    assert knee_population(PATH, 0) == pytest.approx(0.041 / 0.025)
    assert knee_population(PATH, 1.0) == pytest.approx(1.041 / 0.025)


def test_throughput_bounds():
    lower, upper = throughput_bounds(PATH, 1.0, 5)
    assert lower == pytest.approx(5 / (5 * 0.041 + 1.0))
    assert upper == pytest.approx(5 / 1.041)  # still on the light-load side of the knee
    lower, upper = throughput_bounds(PATH, 1.0, 100)
    assert upper == pytest.approx(40.0)  # the bottleneck bound
    assert lower < upper


def test_speeding_up_a_resource_that_is_not_the_bottleneck_changes_nothing():
    name, ceiling = what_if(PATH, "web", 0.5)
    assert (name, ceiling) == ("db", pytest.approx(40.0))


def test_speeding_up_the_bottleneck_moves_it():
    name, ceiling = what_if(PATH, "db", 0.4)  # db demand 0.025 -> 0.010: app (0.012) is next
    assert name == "app"
    assert ceiling == pytest.approx(1 / 0.012)


def test_what_if_does_not_change_its_input():
    what_if(PATH, "db", 0.1)
    assert PATH == {"web": 0.004, "app": 0.012, "db": 0.025}


def test_the_practice_target_in_numbers():
    # One pool of 4 workers, 20 ms each, measured busy 100% at 200 requests per second: D = U / X = 5 ms,
    # which is the 20 ms service time divided by the 4 identical servers.
    d = demand(1.0, 200)
    assert max_throughput({"pool": d}) == pytest.approx(200)
