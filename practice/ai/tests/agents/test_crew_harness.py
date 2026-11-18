"""Checks exercises/agents/crew_harness.py - lesson multi-agent-systems-crewai.

The router is checked through a real ScriptedLLM; the compounding formula against a seeded simulation.
"""

import numpy as np
import pytest

from agents.crew_harness import (
    assert_handed_off,
    calls_by_role,
    chain_success,
    chain_success_with_checks,
    role_router,
)
from llm_fake import ScriptedLLM, count_tokens

pytestmark = pytest.mark.exercise


def ask(llm, role, text):
    return llm.create(messages=[{"role": "user", "content": text}], system=f"You are {role}.\nYour goal: x")


def test_role_router_answers_each_role_in_its_own_order():
    script = {"Fraud Analyst": ["contest"], "Evidence Collector": ["EV-1", "EV-2"]}
    llm = ScriptedLLM(role_router(script))
    assert ask(llm, "Evidence Collector", "a").text == "EV-1"
    assert ask(llm, "Fraud Analyst", "b").text == "contest"
    assert ask(llm, "Evidence Collector", "c").text == "EV-2"
    assert script["Evidence Collector"] == ["EV-1", "EV-2"]  # the caller's lists are not consumed


def test_role_router_supports_tool_steps_and_callables():
    llm = ScriptedLLM(role_router({"Crew Manager": [{"tool": "delegate_work", "input": {"coworker": "A"}},
                                                    lambda req: f"saw {len(req.messages)} messages"]}))
    assert ask(llm, "Crew Manager", "x").stop_reason == "tool_use"
    assert ask(llm, "Crew Manager", "y").text == "saw 1 messages"


def test_role_router_fails_loudly_on_unexpected_calls():
    llm = ScriptedLLM(role_router({"Fraud Analyst": ["contest"]}))
    with pytest.raises(AssertionError, match="Dispute Writer"):
        ask(llm, "Dispute Writer", "x")
    ask(llm, "Fraud Analyst", "x")
    with pytest.raises(AssertionError, match="Fraud Analyst"):
        ask(llm, "Fraud Analyst", "again")


def test_calls_by_role_counts_calls_and_prompt_tokens():
    llm = ScriptedLLM(role_router({"A": ["1", "2"], "B": ["3"]}))
    ask(llm, "B", "hello there")
    ask(llm, "A", "one")
    ask(llm, "A", "two words")
    summary = calls_by_role(llm.calls)
    assert list(summary) == ["B", "A"]
    assert summary["B"] == {"calls": 1, "prompt_tokens": count_tokens("You are B.\nYour goal: x\nhello there")}
    assert summary["A"]["calls"] == 2
    assert summary["A"]["prompt_tokens"] == count_tokens("You are A. Your goal: x one") + count_tokens(
        "You are A. Your goal: x two words"
    )


def test_calls_by_role_reads_block_content():
    llm = ScriptedLLM(["ok"])
    llm.create(
        messages=[{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "EV-1 found"}]}],
        system="You are Crew Manager.",
    )
    assert calls_by_role(llm.calls)["Crew Manager"]["prompt_tokens"] == count_tokens("You are Crew Manager. EV-1 found")


def test_assert_handed_off_finds_the_first_prompt_with_the_text():
    llm = ScriptedLLM(role_router({"Collector": ["EV-1"], "Writer": ["w1", "w2"]}))
    ask(llm, "Collector", "case")
    ask(llm, "Writer", "no context here")
    ask(llm, "Writer", "context: EV-1")
    assert assert_handed_off(llm.calls, "EV-1", "Writer") == 2
    with pytest.raises(AssertionError, match="never received"):
        assert_handed_off(llm.calls, "EV-9", "Writer")
    with pytest.raises(AssertionError, match="never called"):
        assert_handed_off(llm.calls, "EV-1", "Analyst")


def test_chain_success_is_the_product():
    assert chain_success([0.9, 0.9, 0.9, 0.9]) == pytest.approx(0.6561)
    assert chain_success([1.0]) == 1.0
    for bad in ([], [1.2], [-0.1, 0.5]):
        with pytest.raises(ValueError):
            chain_success(bad)


def test_checks_with_retries_follow_the_recurrence():
    assert chain_success_with_checks(0.9, 4, 0.0, 3) == pytest.approx(0.9**4)
    assert chain_success_with_checks(0.9, 1, 0.8, 1) == pytest.approx(0.9 + 0.1 * 0.8 * 0.9)
    assert chain_success_with_checks(0.9, 4, 0.8, 2) == pytest.approx((0.9 + 0.1 * 0.8 * (0.9 + 0.1 * 0.8 * 0.9)) ** 4)
    with pytest.raises(ValueError):
        chain_success_with_checks(0.9, 0, 0.5, 1)
    with pytest.raises(ValueError):
        chain_success_with_checks(0.9, 2, 1.5, 1)


def test_formula_matches_a_seeded_simulation():
    rng = np.random.default_rng(11)
    p, steps, catch, retries, runs = 0.9, 4, 0.8, 2, 20000
    ok = 0
    for _ in range(runs):
        chain_ok = True
        for _ in range(steps):
            for attempt in range(retries + 1):
                right = rng.random() < p
                if right:
                    break
                caught = rng.random() < catch
                if not caught or attempt == retries:
                    chain_ok = False
                    break
            if not chain_ok:
                break
        ok += chain_ok
    assert ok / runs == pytest.approx(chain_success_with_checks(p, steps, catch, retries), abs=0.01)
