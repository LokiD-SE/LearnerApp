"""Checks exercises/specialised/smi_triage.py: scope first, then the test behind the result, then the rest."""

import pytest
from smi_fixture import LABELS, NEXT_STEP, SCAN_REPORT, ScanFinding
from specialised.smi_triage import classify, next_step, report_order, triage

pytestmark = pytest.mark.exercise


def finding(**kw):
    base = dict(id="F-99", title="t", host="portal.sandpay.example", in_scope=True, claimed="medium")
    base.update(kw)
    return ScanFinding(**base)


@pytest.mark.parametrize(
    "kw, label",
    [
        (dict(in_scope=False), "out_of_scope"),
        (dict(in_scope=False, repro="reproduced", control_ok=True), "out_of_scope"),
        (dict(in_scope=False, duplicate_of="F-01"), "out_of_scope"),
        (dict(duplicate_of="F-01", repro="reproduced"), "duplicate"),
        (dict(repro="not_tried"), "unverified"),
        (dict(repro="not_tried", control_ok=False), "unverified"),
        (dict(repro="reproduced", control_ok=False), "invalid_test"),
        (dict(repro="not_reproduced", control_ok=False), "invalid_test"),
        (dict(repro="reproduced"), "confirmed"),
        (dict(repro="not_reproduced"), "false_positive"),
    ],
)
def test_the_first_rule_that_applies_decides(kw, label):
    assert classify(finding(**kw)) == label


def test_a_bad_record_is_refused_even_when_it_is_out_of_scope():
    with pytest.raises(ValueError):
        classify(finding(repro="maybe"))
    with pytest.raises(ValueError):
        classify(finding(claimed="urgent", in_scope=False))


def test_the_sample_report_lands_in_the_expected_labels():
    assert {f.id: classify(f) for f in SCAN_REPORT} == {
        "F-01": "confirmed", "F-02": "confirmed", "F-03": "confirmed", "F-04": "false_positive",
        "F-05": "invalid_test", "F-06": "unverified", "F-07": "unverified", "F-08": "duplicate",
        "F-09": "out_of_scope", "F-10": "confirmed", "F-11": "invalid_test", "F-12": "out_of_scope",
    }


def test_triage_counts_every_label_even_when_empty():
    assert triage([]) == {label: 0 for label in LABELS}
    assert list(triage([])) == list(LABELS)
    assert triage(SCAN_REPORT) == {
        "out_of_scope": 2, "invalid_test": 2, "unverified": 2, "confirmed": 4, "false_positive": 1, "duplicate": 1,
    }


def test_triage_accepts_any_iterable():
    assert triage(iter(SCAN_REPORT))["confirmed"] == 4


def test_next_step_follows_the_order_of_the_work_not_the_size_of_the_bucket():
    counts = triage(SCAN_REPORT)
    assert counts["confirmed"] > counts["out_of_scope"]  # the biggest bucket is not the first job
    assert next_step(counts) == NEXT_STEP["out_of_scope"]


def test_next_step_moves_down_the_list_as_buckets_empty():
    counts = {label: 0 for label in LABELS}
    expected = NEXT_STEP["confirmed"]
    counts["confirmed"] = 3
    counts["duplicate"] = 5
    assert next_step(counts) == expected
    counts["unverified"] = 1
    assert next_step(counts) == NEXT_STEP["unverified"]
    counts["invalid_test"] = 1
    assert next_step(counts) == NEXT_STEP["invalid_test"]
    counts["out_of_scope"] = 1
    assert next_step(counts) == NEXT_STEP["out_of_scope"]


def test_next_step_with_nothing_to_do():
    assert next_step({}) == "Nothing to triage."
    assert next_step({label: 0 for label in LABELS}) == "Nothing to triage."
    assert next_step({"duplicate": 1}) == NEXT_STEP["duplicate"]


def test_the_report_lists_only_confirmed_findings_most_severe_first():
    assert report_order(SCAN_REPORT) == ["F-02", "F-01", "F-03", "F-10"]


def test_equal_severities_are_ordered_by_id_and_other_labels_are_left_out():
    rows = [
        finding(id="F-20", claimed="high", repro="reproduced"),
        finding(id="F-10", claimed="high", repro="reproduced"),
        finding(id="F-30", claimed="critical", repro="not_reproduced"),
        finding(id="F-40", claimed="info", repro="reproduced"),
    ]
    assert report_order(rows) == ["F-10", "F-20", "F-40"]
    assert report_order([]) == []
