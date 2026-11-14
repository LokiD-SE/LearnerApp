"""Checks exercises/genai/approach_eval.py - lesson fine-tuning-vs-rag-vs-prompting."""

import pytest
from genai.approach_eval import (
    ApproachResult,
    choose,
    cost_per_1k_requests,
    discordant,
    run_approach,
    sign_test_p,
)
from llm_fake import ScriptedLLM

pytestmark = pytest.mark.exercise

CASES = [{"q": f"fee for plan {i}?", "answer": f"{i}%"} for i in range(4)]


def build(case):
    return {"messages": [{"role": "user", "content": case["q"]}], "max_tokens": 20}


def grade(case, text):
    return text.strip() == case["answer"]


def result(name, pattern, tin=1000, tout=100):
    return ApproachResult(name, [c == "1" for c in pattern], tin, tout)


class TestRunApproach:
    def test_asks_every_case_in_order_and_grades(self):
        llm = ScriptedLLM(["0%", "9%", "2%", "3%"])
        r = run_approach("prompting", llm, CASES, build, grade)
        assert r.name == "prompting"
        assert r.correct == [True, False, True, True]
        assert r.accuracy == pytest.approx(0.75)
        assert [c.messages[0]["content"] for c in llm.calls] == [c["q"] for c in CASES]

    def test_sums_token_usage_from_the_replies(self):
        llm = ScriptedLLM(lambda req: "1%")
        r = run_approach("p", llm, CASES, build, grade)
        # toy tokenizer: "fee for plan 0 ?" = 5 input tokens; "1%" = 2 output tokens
        assert (r.input_tokens, r.output_tokens) == (4 * 5, 4 * 2)

    def test_uses_the_request_builder(self):
        llm = ScriptedLLM(lambda req: req.system)
        r = run_approach("rag", llm, CASES[:2], lambda c: {**build(c), "system": c["answer"]}, grade)
        assert r.correct == [True, True]
        assert llm.calls[1].system == "1%"


class TestStatistics:
    def test_discordant_pairs(self):
        base = result("b", "11001100")
        cand = result("c", "10111110")
        assert discordant(base, cand) == (3, 1)

    def test_discordant_needs_same_cases(self):
        with pytest.raises(ValueError):
            discordant(result("b", "101"), result("c", "1010"))

    @pytest.mark.parametrize(
        "wins, losses, p",
        [(0, 0, 1.0), (1, 0, 1.0), (5, 0, 0.0625), (6, 0, 0.03125), (8, 2, 0.109375), (2, 8, 0.109375), (15, 3, 0.007538)],
    )
    def test_sign_test(self, wins, losses, p):
        assert sign_test_p(wins, losses) == pytest.approx(p, abs=1e-6)

    def test_cost_per_1k(self):
        r = result("x", "1111", tin=4000, tout=400)  # 1000 in, 100 out per request
        assert cost_per_1k_requests(r, 3.0, 15.0) == pytest.approx(1000 * (1000 * 3 + 100 * 15) / 1e6)
        assert cost_per_1k_requests(ApproachResult("empty"), 3.0, 15.0) == 0.0


PRICES = {"prompting": (3.0, 15.0), "rag": (3.0, 15.0), "fine_tuning": (6.0, 24.0)}


class TestChoose:
    def test_keeps_baseline_when_gain_is_not_significant(self):
        base = result("prompting", "1" * 10 + "0" * 10)
        cand = result("rag", "1" * 10 + "1" * 3 + "0" * 7)  # 3 wins, 0 losses: p = 0.25
        d = choose([base, cand], "prompting", PRICES)
        assert d.choice == "prompting"
        assert len(d.reasons) == 1 and "rag" in d.reasons[0]

    def test_accepts_a_significant_winner(self):
        base = result("prompting", "1" * 10 + "0" * 10)
        cand = result("rag", "1" * 10 + "1" * 8 + "00")  # 8 wins, 0 losses
        assert choose([base, cand], "prompting", PRICES).choice == "rag"

    def test_more_wins_than_losses_is_required(self):
        base = result("prompting", "1" * 20)
        cand = result("rag", "0" * 20)
        assert choose([base, cand], "prompting", PRICES, alpha=1.1).choice == "prompting"

    def test_highest_accuracy_then_lowest_cost(self):
        base = result("prompting", "0" * 20)
        rag = result("rag", "1" * 18 + "00", tin=40_000)
        ft = result("fine_tuning", "1" * 18 + "00", tin=4_000)
        # same accuracy: fine_tuning is cheaper per request despite higher prices
        assert choose([base, rag, ft], "prompting", PRICES).choice == "fine_tuning"
        better_rag = result("rag", "1" * 19 + "0", tin=40_000)
        assert choose([base, better_rag, ft], "prompting", PRICES).choice == "rag"

    def test_regression_guard_rejects_a_candidate_that_forgets(self):
        base = result("prompting", "0" * 20)
        ft = result("fine_tuning", "1" * 20)
        guard = {"prompting": 0.90, "fine_tuning": 0.80}
        d = choose([base, ft], "prompting", PRICES, guard=guard)
        assert d.choice == "prompting"
        assert "fine_tuning" in d.reasons[0]
        assert choose([base, ft], "prompting", PRICES, guard={"prompting": 0.90, "fine_tuning": 0.89}).choice == "fine_tuning"
