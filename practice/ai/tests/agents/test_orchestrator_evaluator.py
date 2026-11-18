"""Checks exercises/agents/orchestrator_evaluator.py - lesson agent-loops-and-workflow-patterns.

ScriptedLLM plays the orchestrator, the workers, the synthesiser, the generator and the LLM evaluator. Workers run
through a sequential map_fn so the script order is fixed.
"""

import json

import pytest

from agents.orchestrator_evaluator import PlanError, evaluate_optimize, llm_evaluator, orchestrate, plan_subtasks
from llm_fake import ScriptedLLM

pytestmark = pytest.mark.exercise

TASK = "Reconcile November payouts for merchants m_12 and m_40"
PLAN = {"subtasks": [{"id": "m-12", "instruction": "Reconcile m_12"}, {"id": "m-40", "instruction": "Reconcile m_40"}]}


def sequential(fn, items):
    return [fn(i) for i in items]


def test_plan_is_parsed_from_prose_and_validated():
    llm = ScriptedLLM(["Here is the plan:\n" + json.dumps(PLAN) + "\nGood luck."])
    assert plan_subtasks(llm, TASK) == PLAN["subtasks"]
    prompt = llm.calls[0].messages[0]["content"]
    assert f"<task>\n{TASK}\n</task>" in prompt and "at most 5" in prompt


@pytest.mark.parametrize(
    "reply",
    [
        "no json here",
        "{not json}",
        json.dumps({"tasks": []}),
        json.dumps({"subtasks": []}),
        json.dumps({"subtasks": [{"id": f"s{i}", "instruction": "x"} for i in range(6)]}),
        json.dumps({"subtasks": [{"id": "Bad Id", "instruction": "x"}]}),
        json.dumps({"subtasks": [{"id": "a", "instruction": ""}]}),
        json.dumps({"subtasks": [{"id": "a", "instruction": "x"}, {"id": "a", "instruction": "y"}]}),
        json.dumps({"subtasks": ["reconcile everything"]}),
    ],
)
def test_bad_plans_are_rejected(reply):
    with pytest.raises(PlanError):
        plan_subtasks(ScriptedLLM([reply]), TASK)


def test_extra_keys_are_dropped():
    plan = {"subtasks": [{"id": "a", "instruction": "x", "tool": "delete_all"}]}
    assert plan_subtasks(ScriptedLLM([json.dumps(plan)]), TASK) == [{"id": "a", "instruction": "x"}]


def test_orchestrate_runs_one_worker_per_subtask_then_synthesises():
    llm = ScriptedLLM([json.dumps(PLAN), "m_12 matches", "m_40 short by 80.00", "One payout is short."])
    out = orchestrate(llm, TASK, map_fn=sequential)
    assert out["plan"] == PLAN["subtasks"]
    assert out["results"] == {"m-12": "m_12 matches", "m-40": "m_40 short by 80.00"}
    assert out["answer"] == "One payout is short."
    prompts = [c.messages[0]["content"] for c in llm.calls]
    assert prompts[1] == f"Overall task: {TASK}\nYour subtask (m-12): Reconcile m_12"
    assert prompts[2] == f"Overall task: {TASK}\nYour subtask (m-40): Reconcile m_40"
    assert '<result id="m-12">\nm_12 matches\n</result>\n<result id="m-40">\nm_40 short by 80.00\n</result>' in prompts[3]
    assert prompts[3].endswith("Combine the results into one answer.")


def test_orchestrate_runs_no_workers_on_a_bad_plan():
    llm = ScriptedLLM(["sorry, I cannot plan this", "worker"])
    with pytest.raises(PlanError):
        orchestrate(llm, TASK, map_fn=sequential)
    assert len(llm.calls) == 1


def must_mention(*facts):
    return lambda draft: [f"missing {f}" for f in facts if f not in draft]


def test_evaluate_optimize_revises_with_feedback_until_accepted():
    llm = ScriptedLLM(["Your payout was short.", "Payout po_1042 was short by 80.00 because of refund rf_7."])
    out = evaluate_optimize(llm, "Write the notice.", must_mention("po_1042", "80.00", "rf_7"))
    assert out["accepted"] is True and out["rounds"] == 2
    assert out["draft"] == "Payout po_1042 was short by 80.00 because of refund rf_7."
    assert out["history"][0]["problems"] == ["missing po_1042", "missing 80.00", "missing rf_7"]
    assert out["history"][1]["problems"] == []
    second = llm.calls[1].messages[0]["content"]
    assert second == (
        "Write the notice.\n<draft>\nYour payout was short.\n</draft>\nFix these problems:\n"
        "- missing po_1042\n- missing 80.00\n- missing rf_7"
    )


def test_evaluate_optimize_gives_up_after_max_rounds():
    llm = ScriptedLLM(["draft 1", "draft 2", "draft 3", "never"])
    out = evaluate_optimize(llm, "t", must_mention("po_1042"), max_rounds=3)
    assert out["accepted"] is False and out["rounds"] == 3 and out["draft"] == "draft 3"
    assert len(llm.calls) == 3


def test_first_draft_accepted_means_one_call():
    llm = ScriptedLLM(["po_1042 ok"])
    assert evaluate_optimize(llm, "t", must_mention("po_1042"))["rounds"] == 1


def test_llm_evaluator_parses_pass_fail_and_nonsense():
    llm = ScriptedLLM(["PASS", "FAIL: no payout id\nFAIL: tone too casual", "Looks fine to me!"])
    evaluate = llm_evaluator(llm, ["Names the payout id.", "Formal tone."])
    assert evaluate("d1") == []
    assert evaluate("d2") == ["no payout id", "tone too casual"]
    assert evaluate("d3") == ["evaluator reply not understood"]
    prompt = llm.calls[0].messages[0]["content"]
    assert "<draft>\nd1\n</draft>" in prompt and "1. Names the payout id.\n2. Formal tone." in prompt
