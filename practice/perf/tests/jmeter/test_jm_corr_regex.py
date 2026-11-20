import random

import pytest
from jmeter.jm_corr_regex import extract, render_template

pytestmark = pytest.mark.exercise

PAGE = '{"data": [{"id": "pay_100001", "amount_minor": 2500}, {"id": "pay_100002", "amount_minor": 990}, {"id": "pay_100003", "amount_minor": 120}], "has_more": true}'
ID = r'"id": "(pay_\d+)"'


def test_template_groups_and_literal_text():
    import re

    m = re.search(r'"id": "(pay_)(\d+)"', PAGE)
    assert render_template("$1$$2$", m) == "pay_100001"
    assert render_template("id=$2$ (from $0$)", m) == 'id=100001 (from "id": "pay_100001")'


def test_first_match_sets_ref_and_groups():
    out = extract({}, PAGE, "pid", ID, match_no=1, default="NOT_FOUND")
    assert out == {"pid": "pay_100001", "pid_g": "1", "pid_g0": '"id": "pay_100001"', "pid_g1": "pay_100001"}


def test_nth_match():
    assert extract({}, PAGE, "pid", ID, match_no=3)["pid"] == "pay_100003"


def test_no_match_sets_default_and_removes_stale_groups():
    before = {"pid": "pay_100001", "pid_g": "1", "pid_g0": "x", "pid_g1": "pay_100001", "other": "kept"}
    out = extract(before, PAGE, "pid", ID, match_no=4, default="PID_NOT_FOUND")
    assert out == {"pid": "PID_NOT_FOUND", "other": "kept"}
    assert before["pid_g1"] == "pay_100001"  # the input dict is not changed


def test_no_match_without_default_leaves_ref_unchanged():
    out = extract({"pid": "pay_100001", "pid_g1": "pay_100001"}, '{"data": []}', "pid", ID)
    assert out == {"pid": "pay_100001"}


def test_random_match_uses_the_given_rng():
    picks = {extract({}, PAGE, "pid", ID, match_no=0, rng=random.Random(seed))["pid"] for seed in range(30)}
    assert picks == {"pay_100001", "pay_100002", "pay_100003"}
    assert extract({}, PAGE, "pid", ID, match_no=0, rng=random.Random(4)) == extract(
        {}, PAGE, "pid", ID, match_no=0, rng=random.Random(4))


def test_negative_match_number_extracts_all_like_jmeter():
    # The same variables JMeter 5.6.3's Debug Sampler showed for this extractor (lesson output).
    out = extract({}, PAGE, "page_id", ID, match_no=-1, default="ID_NOT_FOUND")
    assert out["page_id"] == "ID_NOT_FOUND"
    assert out["page_id_matchNr"] == "3"
    assert [out[f"page_id_{n}"] for n in (1, 2, 3)] == ["pay_100001", "pay_100002", "pay_100003"]
    assert out["page_id_2_g"] == "1" and out["page_id_2_g1"] == "pay_100002"
    assert out["page_id_2_g0"] == '"id": "pay_100002"'
    assert "page_id_g1" not in out


def test_negative_with_no_matches():
    assert extract({}, '{"data": []}', "page_id", ID, match_no=-1, default="NONE") == {
        "page_id_matchNr": "0", "page_id": "NONE"}


def test_two_groups_and_template():
    out = extract({}, PAGE, "row", r'"id": "(pay_\d+)", "amount_minor": (\d+)', template="$1$:$2$", match_no=2)
    assert out["row"] == "pay_100002:990" and out["row_g"] == "2" and out["row_g2"] == "990"
