"""Checks exercises/specialised/smi_estimate.py: a defensible effort estimate from an inventory and stated rates."""

import dataclasses

import pytest
from smi_fixture import PRACTICE_RATES, Estimate, Inventory, Rates
from specialised.smi_estimate import calendar_days, estimate, person_days, effort_hours

pytestmark = pytest.mark.exercise

PORTAL = Inventory(endpoints=17, roles=2, uploads=0, integrations=1)


def test_one_endpoint_one_role_is_hours_per_endpoint_plus_setup():
    assert effort_hours(Inventory(1, 1), PRACTICE_RATES) == pytest.approx(1.5 + 8)


def test_every_extra_role_adds_the_uplift_to_the_endpoint_effort_only():
    assert effort_hours(Inventory(10, 1), PRACTICE_RATES) == pytest.approx(10 * 1.5 + 8)
    assert effort_hours(Inventory(10, 3), PRACTICE_RATES) == pytest.approx(10 * 1.5 * 1.8 + 8)


def test_uploads_and_integrations_are_fixed_hours_not_multiplied_by_roles():
    one = effort_hours(Inventory(0, 4, uploads=2, integrations=3), PRACTICE_RATES)
    assert one == pytest.approx(2 * 6 + 3 * 4 + 8)


def test_the_portal_inventory():
    assert effort_hours(PORTAL, PRACTICE_RATES) == pytest.approx(47.7)


def test_the_estimate_breakdown_adds_report_retest_and_contingency():
    e = estimate(PORTAL, PRACTICE_RATES)
    assert isinstance(e, Estimate)
    assert e.test_hours == pytest.approx(47.7)
    assert e.report_hours == pytest.approx(11.925)
    assert e.retest_hours == pytest.approx(7.155)
    assert e.contingency_hours == pytest.approx(10.017)  # 15% of test + report + retest, not of the test alone
    assert e.total_hours == pytest.approx(76.797)


def test_zero_overheads_leave_only_the_effort_hours():
    rates = dataclasses.replace(PRACTICE_RATES, report_fraction=0, retest_fraction=0, contingency_fraction=0)
    e = estimate(PORTAL, rates)
    assert e.total_hours == pytest.approx(e.test_hours)


def test_person_days_round_up_to_the_next_half_day():
    assert person_days(76.797, 6) == 13.0
    assert person_days(12, 6) == 2.0
    assert person_days(12.5, 6) == 2.5
    assert person_days(13, 6) == 2.5  # 2.1666... -> 2.5
    assert person_days(0, 6) == 0.0


def test_a_float_error_does_not_cost_a_half_day():
    assert person_days(0.1 * 3 * 40, 6) == 2.0  # 0.1 * 3 * 40 is a hair above 12 in floating point


def test_calendar_days_divide_by_testers_times_utilisation_and_round_up():
    assert calendar_days(13.0, 2) == 9  # 13 / (2 * 0.8) = 8.125
    assert calendar_days(13.0, 1) == 17  # 13 / 0.8 = 16.25
    assert calendar_days(8.0, 2, utilisation=1.0) == 4
    assert calendar_days(0, 3) == 0


@pytest.mark.parametrize(
    "bad",
    [
        lambda: effort_hours(Inventory(-1, 1), PRACTICE_RATES),
        lambda: effort_hours(Inventory(5, 0), PRACTICE_RATES),
        lambda: effort_hours(Inventory(5, 1, uploads=-1), PRACTICE_RATES),
        lambda: effort_hours(Inventory(5, 1), dataclasses.replace(PRACTICE_RATES, hours_per_endpoint=-1)),
        lambda: effort_hours(Inventory(5, 1), dataclasses.replace(PRACTICE_RATES, hours_per_day=0)),
        lambda: estimate(Inventory(5, 0), PRACTICE_RATES),
        lambda: person_days(-1, 6),
        lambda: person_days(10, 0),
        lambda: calendar_days(10, 0),
        lambda: calendar_days(10, 2, utilisation=0),
        lambda: calendar_days(10, 2, utilisation=1.2),
        lambda: calendar_days(-1, 2),
    ],
)
def test_nonsense_is_refused_instead_of_estimated(bad):
    with pytest.raises(ValueError):
        bad()


def test_rates_is_a_plain_record():
    assert isinstance(PRACTICE_RATES, Rates) and PRACTICE_RATES.hours_per_day == 6.0
