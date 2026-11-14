"""Checks exercises/genai/prompt_regression.py - lesson prompt-engineering.

The "model" here is a keyword rule written for the test (see ``toy_model``), not a language model: it lets
the tests check the harness - versions, cases, grading, comparison and the gate - deterministically.
"""

import pytest
from genai.prompt_regression import (
    Case,
    CaseResult,
    PromptVersion,
    SuiteResult,
    compare,
    gate,
    grade_label,
    run_suite,
)
from llm_fake import ScriptedLLM

pytestmark = pytest.mark.exercise

RULES = [("stolen", "fraud"), ("dispute", "chargeback"), ("payout", "payout_delay"), ("refund", "refund"),
         ("charged twice", "refund")]


def toy_model(req):
    """Keyword rule: uses only labels named in the system prompt; tags only if the prompt shows the format."""
    text = req.messages[-1]["content"].lower()
    label = next((lab for word, lab in RULES if word in text and lab in req.system), "other")
    return f"<label>{label}</label>" if "<label>" in req.system else label


CASES = [
    Case("dup-charge", "I was charged twice for order 5521", "refund"),
    Case("stolen-card", "My card was stolen and used at a shop", "fraud"),
    Case("bank-dispute", "The customer opened a dispute with their bank", "chargeback"),
    Case("late-payout", "Our payout from Friday has not arrived", "payout_delay"),
    Case("email-change", "How do I change my login email?", "other"),
]
USER = "<ticket>{ticket}</ticket>\n\nWhich category does this ticket belong to?"
V1 = PromptVersion("v1", "Classify the SandPay support ticket.", USER)
V2 = PromptVersion(
    "v2",
    "Categories: refund, fraud, chargeback, payout_delay, other. Reply only <label>category</label>.",
    USER,
)
V3 = PromptVersion("v3", "Categories: refund, fraud, chargeback, other. Reply only <label>category</label>.", USER)


class TestPromptVersion:
    def test_fingerprint_is_12_hex_and_tracks_content_not_name(self):
        fp = V2.fingerprint
        assert len(fp) == 12 and all(c in "0123456789abcdef" for c in fp)
        assert PromptVersion("renamed", V2.system, V2.user_template).fingerprint == fp
        assert PromptVersion("v2", V2.system + " ", USER).fingerprint != fp
        assert PromptVersion("v2", V2.system, USER + " ").fingerprint != fp

    def test_fingerprint_separates_system_from_template(self):
        a = PromptVersion("a", "ab", "c{ticket}")
        b = PromptVersion("b", "a", "bc{ticket}")
        assert a.fingerprint != b.fingerprint

    def test_render_escapes_ticket_and_sets_request(self):
        request = V2.render("a <b> & c")
        assert request["system"] == V2.system
        assert request["messages"] == [
            {"role": "user", "content": "<ticket>a &lt;b&gt; &amp; c</ticket>\n\nWhich category does this ticket belong to?"}
        ]
        assert request["max_tokens"] == 20 and request["temperature"] == 0.0


class TestGrader:
    @pytest.mark.parametrize(
        "reply, expected, result",
        [
            ("<label>refund</label>", "refund", ("refund", True)),
            ("<label>fraud</label>", "refund", ("fraud", False)),
            ("refund", "refund", (None, False)),
            ("<label>refund</label><label>refund</label>", "refund", (None, False)),
        ],
    )
    def test_grade_label(self, reply, expected, result):
        assert grade_label(reply, expected) == result


class TestRunSuite:
    def test_one_call_per_case_in_order(self):
        llm = ScriptedLLM(toy_model)
        result = run_suite(llm, V2, CASES)
        assert len(llm.calls) == len(CASES)
        assert ["charged twice" in c.messages[0]["content"] for c in llm.calls] == [True, False, False, False, False]
        assert result.version == "v2" and result.fingerprint == V2.fingerprint
        assert [r.case_id for r in result.results] == [c.id for c in CASES]
        assert result.pass_rate == 1.0

    def test_bare_prompt_fails_on_format(self):
        result = run_suite(ScriptedLLM(toy_model), V1, CASES)
        assert result.pass_rate == 0.0
        assert all(r.got is None for r in result.results)

    def test_dropped_label_fails_exactly_that_case(self):
        result = run_suite(ScriptedLLM(toy_model), V3, CASES)
        assert result.pass_rate == pytest.approx(0.8)
        failed = [r for r in result.results if not r.passed]
        assert failed == [CaseResult("late-payout", "payout_delay", "other", False)]

    def test_custom_grader_is_used(self):
        # V1 names no labels, so the toy rule answers a bare "other" every time; a bare-word grader accepts it.
        result = run_suite(ScriptedLLM(toy_model), V1, CASES, grader=lambda text, exp: (text, text == exp))
        assert [r.got for r in result.results] == ["other"] * len(CASES)
        assert result.pass_rate == pytest.approx(0.2)

    def test_duplicate_case_ids_rejected(self):
        with pytest.raises(ValueError):
            run_suite(ScriptedLLM(toy_model), V2, [CASES[0], CASES[0]])

    def test_empty_suite_pass_rate_is_zero(self):
        assert SuiteResult("x", "y").pass_rate == 0.0


class TestCompareAndGate:
    def setup_method(self):
        self.r1 = run_suite(ScriptedLLM(toy_model), V1, CASES)
        self.r2 = run_suite(ScriptedLLM(toy_model), V2, CASES)
        self.r3 = run_suite(ScriptedLLM(toy_model), V3, CASES)

    def test_compare(self):
        assert compare(self.r2, self.r3) == {"regressions": ["late-payout"], "fixes": []}
        assert compare(self.r1, self.r2) == {"regressions": [], "fixes": sorted(c.id for c in CASES)}

    def test_gate_accepts_an_improvement(self):
        assert gate(self.r1, self.r2, 0.9) == (True, [])

    def test_gate_blocks_regression_even_above_the_bar(self):
        ok, reasons = gate(self.r2, self.r3, 0.75)
        assert not ok
        assert reasons == ["regressed: late-payout"]

    def test_gate_reports_both_reasons(self):
        ok, reasons = gate(self.r2, self.r3, 0.9)
        assert not ok
        assert reasons == ["pass rate 0.80 is below 0.90", "regressed: late-payout"]
