"""Checks exercises/analysis/fe_lab.py: the four LCP parts, total blocking time and lab against field.

The web.dev total blocking time example (three 51 ms tasks give 3 ms, one 10-second task gives 9950 ms) is in the
tests. The real runs are in support/fe_data/runs.json (Chrome, local checkout page, 21 November 2026); the field
samples are SYNTHETIC."""

import pytest
from fe_fixture import load_exercise, load_json

pytestmark = pytest.mark.exercise

lab = load_exercise("analysis/fe_lab.py")


def task(start, duration):
    return {"startTime": start, "duration": duration}


def test_lcp_parts_add_up_to_the_lcp():
    parts = lab.lcp_parts(100, 150, 500, 520)
    assert parts == {"ttfb": 100, "load_delay": 50, "load_duration": 350, "render_delay": 20}
    assert sum(parts.values()) == pytest.approx(520)


def test_lcp_parts_refuse_an_impossible_order():
    for args in [(100, 50, 500, 520), (100, 150, 90, 520), (100, 150, 500, 400), (-1, 150, 500, 520)]:
        with pytest.raises(ValueError):
            lab.lcp_parts(*args)


def test_dominant_names_the_largest_part_and_the_first_on_a_tie():
    assert lab.dominant({"ttfb": 10, "load_delay": 300, "load_duration": 200, "render_delay": 5}) == "load_delay"
    assert lab.dominant({"ttfb": 100, "load_delay": 100, "load_duration": 100, "render_delay": 100}) == "ttfb"


def test_three_slightly_long_tasks_block_much_less_than_one_very_long_task():
    assert lab.total_blocking_time([task(1000, 51), task(5000, 51), task(9000, 51)], fcp=0) == pytest.approx(3)
    assert lab.total_blocking_time([task(1000, 10000)], fcp=0) == pytest.approx(9950)


def test_a_task_of_exactly_50_ms_is_not_long():
    assert lab.total_blocking_time([task(100, 50), task(300, 50.0)], fcp=0) == 0


def test_only_tasks_from_first_contentful_paint_count_and_until_cuts_the_window():
    tasks = [task(100, 200), task(400, 120), task(900, 80)]
    assert lab.total_blocking_time(tasks, fcp=400) == pytest.approx(70 + 30)  # the task AT fcp counts
    assert lab.total_blocking_time(tasks, fcp=401) == pytest.approx(30)
    assert lab.total_blocking_time(tasks, fcp=400, until=900) == pytest.approx(70)  # a task AT until does not


def test_lab_vs_field_compares_the_median_of_the_runs_with_the_field_p75():
    result = lab.lab_vs_field([1000, 1100, 1050], 1000)
    assert result["lab_median"] == 1050
    assert result["lab_spread"] == 0.095  # (1100 - 1000) / 1050, three decimals
    assert result["ratio"] == 1.05
    assert result["verdict"] == "similar"
    assert lab.lab_vs_field([2000, 2100, 2050], 1000)["verdict"] == "lab slower"
    assert lab.lab_vs_field([500, 520, 510], 1000)["verdict"] == "lab faster"


def test_the_tolerance_edges_count_as_similar():
    assert lab.lab_vs_field([1250], 1000)["verdict"] == "similar"
    assert lab.lab_vs_field([750], 1000)["verdict"] == "similar"
    assert lab.lab_vs_field([1251], 1000)["verdict"] == "lab slower"
    assert lab.lab_vs_field([1000], 1000, tolerance=0.5)["verdict"] == "similar"


def test_lab_vs_field_refuses_no_runs_or_a_useless_field_value():
    with pytest.raises(ValueError):
        lab.lab_vs_field([], 1000)
    with pytest.raises(ValueError):
        lab.lab_vs_field([1000], 0)


def test_the_real_runs_split_lcp_into_a_long_load_delay_for_the_slow_page_and_a_load_duration_for_the_fixed_one():
    runs = load_json("runs.json")
    for r in runs["slow"]:
        parts = lab.lcp_parts(r["ttfb"], r["hero_request_start"], r["hero_response_end"], r["lcp"])
        assert lab.dominant(parts) == "load_duration"
        assert parts["load_delay"] > 250  # the image is asked for late
    for r in runs["fixed"]:
        parts = lab.lcp_parts(r["ttfb"], r["hero_request_start"], r["hero_response_end"], r["lcp"])
        assert parts["load_delay"] < 50


def test_the_real_slow_page_blocks_after_first_paint_and_the_fixed_page_does_not():
    runs = load_json("runs.json")
    slow = [lab.total_blocking_time(r["longtasks"], r["fcp"], until=r["load"]) for r in runs["slow"]]
    fixed = [lab.total_blocking_time(r["longtasks"], r["fcp"], until=r["load"]) for r in runs["fixed"]]
    assert all(140 <= t <= 160 for t in slow)
    assert all(t == 0 for t in fixed)


def test_a_fast_unthrottled_lab_on_localhost_reads_far_faster_than_the_field_p75():
    runs = load_json("runs.json")
    field = load_json("field_samples.json")
    p75 = sorted(s["lcp"] for s in field if s["device"] == "mobile")
    mobile_p75 = p75[-(-75 * len(p75) // 100) - 1]
    result = lab.lab_vs_field([r["lcp"] for r in runs["fixed"]], mobile_p75)
    assert result["verdict"] == "lab faster"
    assert result["lab_spread"] < 0.05
