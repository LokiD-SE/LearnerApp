import pytest
from fundamentals.types_profiles import expected_users_series, ramp_hold, spike, steps, users_at

pytestmark = pytest.mark.exercise


def test_users_at_follows_stages_and_stops():
    stages = [(10, 5, 5.0), (30, 20, 5.0)]
    assert users_at(stages, 0) == 5
    assert users_at(stages, 9.99) == 5
    assert users_at(stages, 10) == 20
    assert users_at(stages, 29.5) == 20
    assert users_at(stages, 30) is None  # what tick() returns to stop the test
    with pytest.raises(ValueError):
        users_at(stages, -1)


def test_ramp_hold():
    assert ramp_hold(10, 4, 60) == [(1.0, 2, 10.0), (2.0, 4, 10.0), (3.0, 6, 10.0), (4.0, 8, 10.0), (64.0, 10, 10.0)]
    assert ramp_hold(3, 0, 5) == [(5.0, 3, 3.0)]
    with pytest.raises(ValueError):
        ramp_hold(0, 4, 60)
    with pytest.raises(ValueError):
        ramp_hold(10, 4, 0)


def test_steps():
    assert steps(10, 10, 60, 4) == [(60, 10, 10.0), (120, 20, 10.0), (180, 30, 10.0), (240, 40, 10.0)]
    with pytest.raises(ValueError):
        steps(10, 0, 60, 4)


def test_spike():
    assert spike(20, 200, 300, 60, 300) == [(300, 20, 20.0), (360, 200, 180.0), (660, 20, 180.0)]
    for bad in [(20, 20, 1, 1, 1), (0, 10, 1, 1, 1), (5, 10, 0, 1, 1), (5, 10, 1, 1, 0)]:
        with pytest.raises(ValueError):
            spike(*bad)


def test_series_for_a_spike():
    assert expected_users_series(spike(2, 8, 3, 2, 2), 8) == [2, 2, 2, 8, 8, 2, 2, None]
