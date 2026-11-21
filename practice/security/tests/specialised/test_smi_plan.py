"""Checks exercises/specialised/smi_plan.py: from what a feature does to the test areas it needs."""

import pytest
from smi_fixture import BASELINE, CATEGORIES, FLAGS, RULES, Feature, Gaps
from specialised.smi_plan import category_of, plan_gaps, required_areas
from wstg_fixture import WSTG_V42_CHECKLIST

pytestmark = pytest.mark.exercise

PAYMENT_LIST = Feature(
    "payment list", has_login=True, keeps_session=True, has_roles=True, object_ids_in_urls=True,
    json_api=True, handles_sensitive_data=True, uses_sql=True,
)
WEBHOOK = Feature("webhook test", has_login=True, json_api=True, fetches_urls=True)


def test_the_categories_are_the_headings_of_the_v42_checklist():
    headings = {
        line.split("|")[1].strip().strip("*")
        for line in WSTG_V42_CHECKLIST.splitlines()
        if line.startswith("| **WSTG-")
    }
    assert set(CATEGORIES) == headings


def test_every_rule_names_a_real_flag_and_real_categories():
    assert set(RULES) == set(FLAGS)
    assert all(c in CATEGORIES for cats in RULES.values() for c in cats)


@pytest.mark.parametrize("ref", CATEGORIES)
def test_a_category_heading_maps_to_itself(ref):
    assert category_of(ref) == ref


@pytest.mark.parametrize(
    "ref, heading",
    [
        ("WSTG-ATHZ-04", "WSTG-ATHZ"),
        ("WSTG-INPV-05", "WSTG-INPV"),
        ("WSTG-SESS-05", "WSTG-SESS"),
        ("WSTG-APIT-01", "WSTG-APIT"),
        ("WSTG-BUSL-05", "WSTG-BUSLOGIC"),  # the tests are BUSL, the heading is BUSLOGIC
        ("WSTG-CLNT-04", "WSTG-CLIENT"),  # the tests are CLNT, the heading is CLIENT
    ],
)
def test_a_test_id_maps_to_its_heading(ref, heading):
    assert category_of(ref) == heading


@pytest.mark.parametrize("ref", ["WSTG-ATHZ-4", "WSTG-ATHZ-004", "wstg-athz-04", "WSTG-XXXX-01", "WSTG-BUSLOGIC-01", "", "ATHZ"])
def test_anything_else_is_refused(ref):
    with pytest.raises(ValueError):
        category_of(ref)


def test_a_feature_with_no_flags_needs_only_the_baseline():
    assert required_areas(Feature("static page")) == {c: ["baseline"] for c in BASELINE}


def test_each_flag_adds_its_categories_with_its_name_as_the_reason():
    for flag in FLAGS:
        areas = required_areas(Feature("one flag", **{flag: True}))
        for category in RULES[flag]:
            assert flag in areas[category]
        assert set(areas) == set(BASELINE) | set(RULES[flag])


def test_a_category_called_for_twice_lists_both_reasons_sorted():
    areas = required_areas(PAYMENT_LIST)
    assert areas["WSTG-ATHZ"] == ["has_roles", "object_ids_in_urls"]
    assert areas["WSTG-INPV"] == ["json_api", "uses_sql"]


def test_a_baseline_category_keeps_the_baseline_reason_among_the_others():
    assert required_areas(Feature("page", renders_user_input=True))["WSTG-CLIENT"] == ["renders_user_input"]
    assert required_areas(Feature("page", handles_sensitive_data=True))["WSTG-INFO"] == ["baseline"]


def test_the_result_follows_the_order_of_the_categories():
    keys = list(required_areas(PAYMENT_LIST))
    assert keys == [c for c in CATEGORIES if c in keys]
    assert keys == [
        "WSTG-INFO", "WSTG-CONF", "WSTG-IDNT", "WSTG-ATHN", "WSTG-ATHZ", "WSTG-SESS",
        "WSTG-INPV", "WSTG-ERRH", "WSTG-CRYP", "WSTG-APIT",
    ]


def test_a_complete_plan_has_no_gaps():
    plan = ["WSTG-INFO-02", "WSTG-CONF-06", "WSTG-IDNT-04", "WSTG-ATHN-03", "WSTG-INPV-19", "WSTG-ERRH-01",
            "WSTG-APIT-01"]
    assert plan_gaps(WEBHOOK, plan) == Gaps(missing=(), unneeded=())


def test_missing_categories_are_reported_in_checklist_order():
    gaps = plan_gaps(PAYMENT_LIST, ["WSTG-INFO", "WSTG-ATHN-03", "WSTG-INPV-05"])
    assert gaps.missing == ("WSTG-CONF", "WSTG-IDNT", "WSTG-ATHZ", "WSTG-SESS", "WSTG-ERRH", "WSTG-CRYP", "WSTG-APIT")
    assert gaps.unneeded == ()


def test_unneeded_categories_are_reported_and_repeats_count_once():
    gaps = plan_gaps(WEBHOOK, ["WSTG-CLNT-04", "WSTG-CLNT-09", "WSTG-BUSL-05", "WSTG-INFO", "WSTG-INFO-02"])
    assert gaps.unneeded == ("WSTG-BUSLOGIC", "WSTG-CLIENT")
    assert "WSTG-INFO" not in gaps.missing


def test_a_test_id_and_its_heading_cover_the_same_category():
    assert plan_gaps(Feature("f", moves_money=True), ["WSTG-BUSL-05"]).missing == ("WSTG-INFO", "WSTG-CONF", "WSTG-ERRH")


def test_an_unknown_entry_in_the_plan_is_refused():
    with pytest.raises(ValueError):
        plan_gaps(WEBHOOK, ["WSTG-INFO", "WSTG-NOPE-01"])


def test_an_empty_plan_misses_everything_needed():
    assert plan_gaps(WEBHOOK, []).missing == tuple(c for c in CATEGORIES if c in required_areas(WEBHOOK))
