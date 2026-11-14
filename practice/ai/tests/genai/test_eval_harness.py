"""Checks exercises/genai/eval_harness.py - lesson llm-evaluation-and-guardrails.

The "model" is the offline ScriptedLLM, so these tests check the harness: graders, the run loop, Wilson intervals
(against SciPy) and the paired comparison (against SciPy's exact binomial test).
"""

import pytest
from scipy.stats import binomtest

from genai.eval_harness import (
    GoldenCase,
    compare,
    grade,
    grade_exact,
    grade_json_field,
    grade_regex,
    mcnemar_exact_p,
    run_eval,
    summarise,
    wilson_interval,
)
from llm_fake import RateLimitError, ScriptedLLM

pytestmark = pytest.mark.exercise


def test_exact_grader_normalises_case_whitespace_and_a_final_full_stop():
    assert grade_exact("  Disputes.\n", "disputes").passed
    assert grade_exact("EUR", "eur").passed
    assert grade_exact("two   business days", "Two business days").passed


def test_exact_grader_fails_on_a_different_answer_and_says_why():
    g = grade_exact("dispute", "disputes")
    assert not g.passed
    assert "disputes" in g.reason and "dispute" in g.reason


def test_regex_grader_searches_case_insensitively():
    assert grade_regex("Refunds are possible within 180 days of the payment.", r"\b180 days\b").passed
    assert not grade_regex("Refunds are possible within 18 days.", r"\b180 days\b").passed


def test_json_field_grader_reads_a_dotted_path():
    out = '{"intent": "refunds", "refund": {"eligible": true}}'
    assert grade_json_field(out, "intent", "refunds").passed
    assert grade_json_field(out, "refund.eligible", True).passed
    g = grade_json_field(out, "refund.eligible", False)
    assert not g.passed and "expected False" in g.reason


@pytest.mark.parametrize(
    "output, reason",
    [
        ('```json\n{"intent": "refunds"}\n```', "not valid JSON"),
        ("Sure! The intent is refunds.", "not valid JSON"),
        ('{"label": "refunds"}', "missing field"),
        ('["refunds"]', "not a JSON object"),
    ],
)
def test_json_field_grader_fails_without_raising(output, reason):
    g = grade_json_field(output, "intent", "refunds")
    assert not g.passed
    assert reason in g.reason


def test_grade_dispatches_and_rejects_unknown_graders():
    assert grade(GoldenCase("c1", "x", r"\d+ days", grader="regex"), "within 180 days").passed
    assert grade(GoldenCase("c2", "x", "fees", grader="json_field", field="intent"), '{"intent": "fees"}').passed
    with pytest.raises(ValueError):
        grade(GoldenCase("c3", "x", "y", grader="semantic"), "y")
    with pytest.raises(ValueError):
        grade(GoldenCase("c4", "x", "y", grader="json_field"), '{"y": 1}')


def test_run_eval_sends_each_input_at_temperature_zero_and_grades_it():
    cases = [
        GoldenCase("a", "Where is my payout?", "payouts", tags=("intent",)),
        GoldenCase("b", "I was charged twice", "refunds", tags=("intent",)),
    ]
    llm = ScriptedLLM(["payouts", "disputes"])
    results = run_eval(llm, cases, system="Classify.", build_prompt=lambda t: f"<message>{t}</message>")
    assert [r["passed"] for r in results] == [True, False]
    assert llm.calls[0].messages[0]["content"] == "<message>Where is my payout?</message>"
    assert llm.calls[1].system == "Classify."
    assert all(c.temperature == 0.0 for c in llm.calls)
    assert results[1]["output"] == "disputes" and results[1]["tags"] == ("intent",)


def test_run_eval_records_an_api_error_as_a_failed_case_and_continues():
    cases = [GoldenCase("a", "x", "fees"), GoldenCase("b", "y", "fees")]
    results = run_eval(ScriptedLLM([RateLimitError(retry_after=3), "fees"]), cases, "s", lambda t: t)
    assert results[0]["error"] is True and results[0]["passed"] is False and results[0]["output"] is None
    assert results[1]["passed"] is True and results[1]["error"] is False


@pytest.mark.parametrize("passed, n", [(29, 40), (34, 40), (40, 40), (0, 12), (320, 400)])
def test_wilson_interval_matches_scipy(passed, n):
    expected = binomtest(passed, n).proportion_ci(confidence_level=0.95, method="wilson")
    lo, hi = wilson_interval(passed, n)
    assert lo == pytest.approx(expected.low, abs=2e-4)
    assert hi == pytest.approx(expected.high, abs=2e-4)


def test_wilson_interval_stays_inside_zero_and_one_and_checks_its_input():
    lo, hi = wilson_interval(10, 10)
    assert 0 < lo < 1 and hi == pytest.approx(1.0)
    with pytest.raises(ValueError):
        wilson_interval(0, 0)
    with pytest.raises(ValueError):
        wilson_interval(11, 10)


def test_summarise_counts_errors_and_tags():
    results = [
        {"id": "a", "passed": True, "tags": ("intent",), "error": False},
        {"id": "b", "passed": False, "tags": ("intent", "json"), "error": True},
        {"id": "c", "passed": True, "tags": ("json",), "error": False},
        {"id": "d", "passed": True, "tags": (), "error": False},
    ]
    s = summarise(results)
    assert (s["n"], s["passed"], s["errors"]) == (4, 3, 1)
    assert s["pass_rate"] == pytest.approx(0.75)
    assert s["by_tag"] == {"intent": (1, 2), "json": (1, 2)}
    assert s["ci"] == pytest.approx(wilson_interval(3, 4))


@pytest.mark.parametrize("only_a, only_b", [(1, 6), (3, 3), (0, 9), (10, 2), (2, 0)])
def test_mcnemar_exact_p_is_a_binomial_test_of_the_discordant_pairs(only_a, only_b):
    assert mcnemar_exact_p(only_a, only_b) == pytest.approx(binomtest(only_a, only_a + only_b, 0.5).pvalue)


def test_mcnemar_with_no_discordant_pairs_is_one():
    assert mcnemar_exact_p(0, 0) == 1.0


def test_compare_lists_fixes_and_regressions_by_id():
    a = [{"id": i, "passed": p} for i, p in zip("abcdef", [True, True, False, False, True, False])]
    b = [{"id": i, "passed": p} for i, p in zip("abcdef", [True, False, True, True, True, False])]
    c = compare(a, b)
    assert c["both"] == 2 and c["neither"] == 1
    assert c["fixes"] == ["c", "d"] and c["regressions"] == ["b"]
    assert c["p_value"] == pytest.approx(binomtest(1, 3, 0.5).pvalue)


def test_compare_refuses_runs_over_different_cases():
    a = [{"id": "a", "passed": True}, {"id": "b", "passed": True}]
    with pytest.raises(ValueError):
        compare(a, [{"id": "a", "passed": True}, {"id": "c", "passed": True}])
    with pytest.raises(ValueError):
        compare(a, [{"id": "a", "passed": True}, {"id": "a", "passed": False}, {"id": "b", "passed": True}])
