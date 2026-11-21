"""Checks exercises/analysis/fe_vitals.py: rating a metric, the 75th percentile, CLS session windows and a page verdict.

The real data is support/fe_data/runs.json (layout shifts from real Chrome runs of the local checkout page, captured on
21 November 2026). The field samples in support/fe_data/field_samples.json are SYNTHETIC: a seeded mix of mobile and
desktop visits made up for the lesson."""

import pytest
from fe_fixture import load_exercise, load_json

pytestmark = pytest.mark.exercise

vitals = load_exercise("analysis/fe_vitals.py")


def shift(start, value, recent=False):
    return {"startTime": start, "value": value, "hadRecentInput": recent}


def test_each_metric_has_its_own_limits_and_the_limit_itself_is_good():
    assert [vitals.rate("lcp", v) for v in (2500, 2501, 4000, 4001)] == ["good", "needs improvement", "needs improvement", "poor"]
    assert [vitals.rate("inp", v) for v in (200, 201, 500, 501)] == ["good", "needs improvement", "needs improvement", "poor"]
    assert [vitals.rate("cls", v) for v in (0, 0.1, 0.11, 0.25, 0.26)] == [
        "good",
        "good",
        "needs improvement",
        "needs improvement",
        "poor",
    ]


def test_rate_refuses_an_unknown_metric_or_a_negative_value():
    with pytest.raises(ValueError):
        vitals.rate("fid", 50)
    with pytest.raises(ValueError):
        vitals.rate("lcp", -1)


def test_percentile_is_nearest_rank():
    # ten values: rank ceil(0.75 * 10) = 8, so the 8th smallest
    assert vitals.percentile([10, 1, 9, 2, 8, 3, 7, 4, 6, 5], 75) == 8
    assert vitals.percentile([5], 75) == 5
    assert vitals.percentile([1, 2, 3, 4], 100) == 4
    assert vitals.percentile([1, 2, 3, 4], 75) == 3  # ceil(3.0) = 3
    with pytest.raises(ValueError):
        vitals.percentile([], 75)


def test_cls_is_zero_without_shifts_and_ignores_shifts_after_input():
    assert vitals.cls([]) == 0
    assert vitals.cls([shift(100, 0.5, recent=True)]) == 0
    assert vitals.cls([shift(100, 0.5, recent=True), shift(300, 0.05)]) == pytest.approx(0.05)


def test_cls_adds_shifts_that_are_less_than_a_second_apart():
    assert vitals.cls([shift(100, 0.05), shift(600, 0.03), shift(1500, 0.02)]) == pytest.approx(0.10)


def test_cls_takes_the_largest_session_window_not_the_sum_of_all():
    # a gap of 1500 ms closes the first window (0.06); the second window is 0.09
    shifts = [shift(0, 0.03), shift(400, 0.03), shift(1900, 0.04), shift(2300, 0.05)]
    assert vitals.cls(shifts) == pytest.approx(0.09)


def test_cls_closes_a_window_after_five_seconds_even_with_small_gaps():
    # a shift every 900 ms: the shifts at 0..4500 form one window (6 x 0.01); 5400 opens a new one
    shifts = [shift(t, 0.01) for t in range(0, 6000, 900)]
    assert vitals.cls(shifts) == pytest.approx(0.06)


def test_cls_does_not_depend_on_the_order_of_the_entries():
    shifts = [shift(1900, 0.04), shift(0, 0.03), shift(2300, 0.05), shift(400, 0.03)]
    assert vitals.cls(shifts) == pytest.approx(0.09)


def test_assess_uses_the_75th_percentile_and_skips_missing_values():
    samples = [
        {"device": "d", "lcp": 1000, "inp": None, "cls": 0.0},
        {"device": "d", "lcp": 2000, "inp": 100, "cls": 0.05},
        {"device": "d", "lcp": 3000, "inp": 150, "cls": 0.08},
        {"device": "d", "lcp": 9000, "inp": 300, "cls": 0.5},
    ]
    result = vitals.assess(samples)
    assert result["lcp"] == {"p75": 3000, "rating": "needs improvement", "n": 4}
    assert result["inp"] == {"p75": 300, "rating": "needs improvement", "n": 3}
    assert result["cls"]["p75"] == pytest.approx(0.08)
    assert result["cls"]["rating"] == "good"
    assert result["passes"] is False


def test_a_page_passes_only_when_all_three_metrics_are_good():
    good = [{"device": "d", "lcp": 1500, "inp": 100, "cls": 0.02} for _ in range(8)]
    assert vitals.assess(good)["passes"] is True
    worse_cls = good + [{"device": "d", "lcp": 1500, "inp": 100, "cls": 0.4} for _ in range(8)]
    assert vitals.assess(worse_cls)["passes"] is False


def test_a_metric_nobody_measured_does_not_pass():
    result = vitals.assess([{"device": "d", "lcp": 1000, "inp": None, "cls": 0.0}])
    assert result["inp"] == {"p75": None, "rating": None, "n": 0}
    assert result["passes"] is False


def test_distribution_counts_each_rating():
    samples = [{"lcp": v} for v in (1000, 2000, 2500, 3000, 5000)]
    dist = vitals.distribution(samples, "lcp")
    assert dist["good"] == pytest.approx(0.6)
    assert dist["needs improvement"] == pytest.approx(0.2)
    assert dist["poor"] == pytest.approx(0.2)
    assert vitals.distribution([], "lcp") == {"good": 0.0, "needs improvement": 0.0, "poor": 0.0}


def test_segmenting_the_synthetic_field_data_separates_desktop_from_mobile():
    field = load_json("field_samples.json")
    by_device = vitals.segment(field)
    assert set(by_device) == {"mobile", "desktop"}
    assert by_device["desktop"]["passes"] is True
    assert by_device["mobile"]["passes"] is False
    assert by_device["mobile"]["lcp"]["rating"] == "needs improvement"
    # the blended 75th percentile sits between the two segments
    blended = vitals.assess(field)["lcp"]["p75"]
    assert by_device["desktop"]["lcp"]["p75"] < blended < by_device["mobile"]["lcp"]["p75"]


def test_the_real_chrome_runs_the_slow_page_shifts_and_the_fixed_page_does_not():
    runs = load_json("runs.json")
    slow = [vitals.cls(r["shifts"]) for r in runs["slow"]]
    fixed = [vitals.cls(r["shifts"]) for r in runs["fixed"]]
    assert all(vitals.rate("cls", v) == "needs improvement" for v in slow)
    assert all(v == 0 for v in fixed)
