import pytest
from fundamentals.types_classify import PASS_CRITERIA, TYPES, classify

pytestmark = pytest.mark.exercise

EXPECTED = 100  # the specified peak: 100 virtual users


@pytest.mark.parametrize(
    ("stages", "kind"),
    [
        ([(60, 2)], "smoke"),  # 2 users, 1 minute
        ([(300, 10)], "smoke"),  # exactly 10% for exactly 300 s is still a smoke test
        ([(600, 50), (1800, 100)], "load"),  # up to the expected load
        ([(600, 100), (1800, 150), (600, 100)], "stress"),  # above it for a long time
        ([(1800, 80), (120, 300), (1800, 80)], "spike"),  # a short burst, then back
        ([(14_400, 90)], "soak"),  # four hours at a normal load
        ([(300, 50), (300, 100), (300, 150), (300, 200)], "breakpoint"),  # keeps rising
    ],
)
def test_each_type(stages, kind):
    assert classify(stages, EXPECTED) == kind


def test_rules_apply_in_order():
    # four rising stages that stay tiny are a smoke test (rule 1 before rule 2)
    assert classify([(10, 1), (10, 2), (10, 3), (10, 4)], 100) == "smoke"
    # a long run above the expected load is stress, not soak (soak needs peak <= expected)
    assert classify([(14_400, 120)], 100) == "stress"
    # a rising staircase with a spike shape still counts as breakpoint: users never go down
    assert classify([(100, 10), (100, 20), (100, 30), (100, 400)], 100) == "breakpoint"


def test_spike_edges():
    # burst too long (more than 10% of the run): stress, not spike
    assert classify([(600, 80), (300, 300), (600, 80)], 100) == "stress"
    # burst not high enough (below 2x expected): stress
    assert classify([(1800, 80), (60, 150), (1800, 80)], 100) == "stress"
    # no return to normal afterwards: stress
    assert classify([(1800, 80), (60, 300), (1800, 150)], 100) == "stress"


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        classify([], 100)
    with pytest.raises(ValueError):
        classify([(60, 5)], 0)


def test_every_type_has_pass_criteria():
    assert set(PASS_CRITERIA) == set(TYPES)
