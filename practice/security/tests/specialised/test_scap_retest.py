"""Checks exercises/specialised/scap_retest.py: compare an assessment with its retest."""

import pytest
from scap_fixture import Assessment, Result
from specialised.scap_retest import clean_bill, exit_code, retest

pytestmark = pytest.mark.exercise


def assessment(**statuses):
    return Assessment(tuple(Result(flaw.replace("_", "-"), status, f"{status} evidence") for flaw, status in statuses.items()))


@pytest.mark.parametrize("before, after, outcome", [
    ("found", "not-found", "fixed"),
    ("found", "found", "still-open"),
    ("not-found", "found", "new"),
    ("inconclusive", "found", "new"),
    ("blocked", "found", "new"),
    ("not-run", "found", "new"),
    ("not-found", "not-found", "unchanged"),
    ("inconclusive", "not-found", "newly-tested"),
    ("blocked", "not-found", "newly-tested"),
    ("not-run", "not-found", "newly-tested"),
    ("found", "inconclusive", "unverified"),
    ("found", "blocked", "unverified"),
    ("found", "not-run", "unverified"),
    ("not-found", "inconclusive", "unverified"),
    ("not-found", "not-run", "unverified"),
    ("inconclusive", "inconclusive", "unverified"),
])
def test_each_pair_of_statuses_has_one_outcome(before, after, outcome):
    assert [o.outcome for o in retest(assessment(idor=before), assessment(idor=after))] == [outcome]


def test_a_flaw_missing_from_the_retest_is_unverified_never_fixed():
    out = retest(assessment(idor="found", sqli="found"), assessment(idor="not-found"))
    assert {o.flaw: o.outcome for o in out} == {"idor": "fixed", "sqli": "unverified"}


def test_a_flaw_that_is_new_in_the_retest_is_reported():
    out = retest(assessment(idor="found"), assessment(idor="not-found", sqli="found", csrf="not-found"))
    assert [(o.flaw, o.outcome) for o in out] == [("idor", "fixed"), ("sqli", "new"), ("csrf", "newly-tested")]


def test_the_order_is_before_first_then_the_flaws_only_in_the_retest():
    out = retest(assessment(sqli="found", idor="found"), assessment(zzz="found", idor="found", sqli="found"))
    assert [o.flaw for o in out] == ["sqli", "idor", "zzz"]


def test_every_outcome_has_a_note():
    out = retest(assessment(idor="found", sqli="found"), assessment(idor="not-found"))
    assert all(isinstance(o.note, str) and o.note for o in out)


@pytest.mark.parametrize("statuses, expected, clean", [
    ({"idor": "not-found", "sqli": "not-found"}, ["idor", "sqli"], True),
    ({"idor": "not-found", "sqli": "found"}, ["idor", "sqli"], False),
    ({"idor": "not-found", "sqli": "inconclusive"}, ["idor", "sqli"], False),
    ({"idor": "not-found", "sqli": "blocked"}, ["idor", "sqli"], False),
    ({"idor": "not-found", "sqli": "not-run"}, ["idor", "sqli"], False),
    ({"idor": "not-found"}, ["idor", "sqli"], False),  # not tested at all
    ({"idor": "not-found", "sqli": "found"}, ["idor"], True),  # sqli is not part of the claim
    ({}, [], True),
])
def test_a_clean_bill_needs_every_expected_flaw_tested_and_not_found(statuses, expected, clean):
    assert clean_bill(assessment(**statuses), expected) is clean


def outcomes(**kinds):
    from scap_fixture import Retest

    return [Retest(flaw.replace("_", "-"), kind, "") for flaw, kind in kinds.items()]


@pytest.mark.parametrize("kinds, code", [
    ({"a": "fixed", "b": "unchanged", "c": "newly-tested"}, 0),
    ({"a": "fixed", "b": "unverified"}, 2),
    ({"a": "fixed", "b": "still-open"}, 1),
    ({"a": "unchanged", "b": "new"}, 1),
    ({"a": "unverified", "b": "still-open"}, 1),  # a failure outranks an unknown
    ({}, 0),
])
def test_the_exit_code_for_a_pipeline(kinds, code):
    assert exit_code(outcomes(**kinds)) == code
