"""Checks exercises/agents/mini_crew.py - lesson multi-agent-systems-crewai.

A SandPay chargeback-investigation crew (all data fictional) runs against offline ScriptedLLM clients, one per
agent, so every prompt each agent saw can be inspected in ``llm.calls``.
"""

import json

import pytest

from agents.mini_crew import (
    Agent,
    Crew,
    GuardrailError,
    Process,
    Task,
    TaskOutput,
    agent_system_prompt,
    fill_inputs,
    task_prompt,
)
from llm_fake import ScriptedLLM, count_tokens

pytestmark = pytest.mark.exercise

CASE = "Chargeback CB-2041 on payment pay_7Qm2Xc91, 84.00 EUR, reason: goods not received."


def make_agents(collector_script, analyst_script, writer_script):
    collector = Agent(
        "Evidence Collector",
        "List every piece of evidence in the case file with its id",
        "You work in SandPay's disputes team and never guess.",
        ScriptedLLM(collector_script),
    )
    analyst = Agent(
        "Fraud Analyst",
        "Decide whether the chargeback should be contested",
        "You weigh delivery proof, authentication and refund history.",
        ScriptedLLM(analyst_script),
    )
    writer = Agent(
        "Dispute Writer",
        "Write the response to the card scheme",
        "You write short, factual dispute responses.",
        ScriptedLLM(writer_script),
        max_tokens=120,
    )
    return collector, analyst, writer


def make_tasks(collector, analyst, writer, **overrides):
    collect = Task("collect", "Collect the evidence for {case}", "A list of evidence ids with one line each", collector)
    assess = Task("assess", "Assess {case}", "contest or accept, with the evidence ids used", analyst)
    write = Task("write", "Write the response for {case}", "A response of at most 120 words", writer, **overrides)
    return collect, assess, write


def test_agent_system_prompt_has_role_goal_and_backstory():
    collector, _, _ = make_agents([], [], [])
    assert agent_system_prompt(collector) == (
        "You are Evidence Collector.\n"
        "Your goal: List every piece of evidence in the case file with its id\n"
        "You work in SandPay's disputes team and never guess."
    )


def test_task_prompt_without_and_with_context():
    collector, _, _ = make_agents([], [], [])
    task = Task("collect", "Collect it", "A list", collector)
    assert task_prompt(task, []) == "Task: Collect it\n\nExpected output: A list"
    ctx = [TaskOutput("a", "Role A", "out A"), TaskOutput("b", "Role B", "out B")]
    assert task_prompt(task, ctx) == (
        "Task: Collect it\n\nExpected output: A list\n\nContext from earlier tasks:\n"
        '<context task="a" agent="Role A">\nout A\n</context>\n'
        '<context task="b" agent="Role B">\nout B\n</context>'
    )


def test_fill_inputs_replaces_placeholders_and_names_a_missing_one():
    assert fill_inputs("Assess {case} now", {"case": "CB-1"}) == "Assess CB-1 now"
    with pytest.raises(KeyError, match="case"):
        fill_inputs("Assess {case}", {})


def test_sequential_kickoff_runs_in_order_and_passes_the_previous_output():
    collector, analyst, writer = make_agents(
        ["EV-1 delivery scan\nEV-2 3DS passed"], ["contest: EV-1, EV-2"], ["We contest CB-2041."]
    )
    tasks = make_tasks(collector, analyst, writer)
    out = Crew([collector, analyst, writer], list(tasks)).kickoff({"case": CASE})
    assert [t.name for t in out.tasks_output] == ["collect", "assess", "write"]
    assert [t.agent for t in out.tasks_output] == ["Evidence Collector", "Fraud Analyst", "Dispute Writer"]
    assert out.raw == "We contest CB-2041."
    first = collector.llm.calls[0]
    assert first.messages == [
        {"role": "user", "content": f"Task: Collect the evidence for {CASE}\n\nExpected output: A list of evidence ids with one line each"}
    ]
    assert first.system == agent_system_prompt(collector)
    assert first.temperature == 0.0
    assess_prompt = analyst.llm.calls[0].messages[0]["content"]
    assert '<context task="collect" agent="Evidence Collector">\nEV-1 delivery scan\nEV-2 3DS passed\n</context>' in assess_prompt
    write_prompt = writer.llm.calls[0].messages[0]["content"]
    assert "contest: EV-1, EV-2" in write_prompt
    assert "EV-1 delivery scan" not in write_prompt  # default context is the previous task only
    assert writer.llm.calls[0].max_tokens == 120


def test_explicit_context_list_and_empty_context():
    collector, analyst, writer = make_agents(["EVIDENCE"], ["DECISION"], ["LETTER"])
    collect, assess, _ = make_tasks(collector, analyst, writer)
    write = Task("write", "Write it", "A letter", writer, context=[assess, collect])
    assess.context = []
    Crew([collector, analyst, writer], [collect, assess, write]).kickoff({"case": CASE})
    assert "Context from earlier tasks" not in analyst.llm.calls[0].messages[0]["content"]
    prompt = writer.llm.calls[0].messages[0]["content"]
    assert prompt.index('<context task="assess"') < prompt.index('<context task="collect"')
    assert "DECISION" in prompt and "EVIDENCE" in prompt


def word_limit(output):
    words = len(output.raw.split())
    return (True, output.raw.strip()) if words <= 5 else (False, f"{words} words, the limit is 5")


def test_guardrail_feeds_the_error_back_and_retries():
    collector, analyst, writer = make_agents(
        ["EV-1"], ["contest"], ["We contest this chargeback because the parcel was delivered.", "We contest: delivered. "]
    )
    tasks = make_tasks(collector, analyst, writer, guardrails=[word_limit])
    out = Crew([collector, analyst, writer], list(tasks)).kickoff({"case": CASE})
    last = out.tasks_output[-1]
    assert last.attempts == 2
    assert last.value == "We contest: delivered."
    retry = writer.llm.calls[1].messages
    assert retry[1] == {"role": "assistant", "content": "We contest this chargeback because the parcel was delivered."}
    assert retry[2] == {"role": "user", "content": "Your answer failed a check: 9 words, the limit is 5\nReturn a corrected answer."}


def test_guardrail_gives_up_after_max_retries():
    collector, analyst, writer = make_agents(["EV-1"], ["contest"], ["one two three four five six"] * 3)
    tasks = make_tasks(collector, analyst, writer, guardrails=[word_limit], guardrail_max_retries=2)
    with pytest.raises(GuardrailError) as info:
        Crew([collector, analyst, writer], list(tasks)).kickoff({"case": CASE})
    assert info.value.attempts == 3
    assert info.value.task_name == "write"
    assert "6 words" in info.value.error
    assert len(writer.llm.calls) == 3


def test_guardrails_chain_and_transform_the_value():
    def parse_json(output):
        try:
            return True, json.loads(output.raw)
        except json.JSONDecodeError:
            return False, "not valid JSON"

    def known_evidence(output):
        unknown = [e for e in output.value["evidence"] if e not in {"EV-1", "EV-2"}]
        return (False, f"unknown evidence ids {unknown}") if unknown else (True, output.value)

    collector, analyst, writer = make_agents(
        ["EV-1, EV-2"],
        ['```json\n{"decision": "contest"}\n```', '{"decision": "contest", "evidence": ["EV-1", "EV-9"]}',
         '{"decision": "contest", "evidence": ["EV-1", "EV-2"]}'],
        ["Letter"],
    )
    collect, _, write = make_tasks(collector, analyst, writer)
    assess = Task("assess", "Assess {case}", "JSON", analyst, guardrails=[parse_json, known_evidence])
    out = Crew([collector, analyst, writer], [collect, assess, write]).kickoff({"case": CASE})
    assessed = out.tasks_output[1]
    assert assessed.attempts == 3
    assert assessed.value == {"decision": "contest", "evidence": ["EV-1", "EV-2"]}
    feedback = [m["content"] for m in analyst.llm.calls[2].messages if m["role"] == "user"]
    assert feedback[1] == "Your answer failed a check: not valid JSON\nReturn a corrected answer."
    assert feedback[2] == "Your answer failed a check: unknown evidence ids ['EV-9']\nReturn a corrected answer."


def test_token_usage_adds_up_every_call():
    collector, analyst, writer = make_agents(["EV-1"], ["contest"], ["too many words in this reply", "ok"])
    tasks = make_tasks(collector, analyst, writer, guardrails=[word_limit])
    out = Crew([collector, analyst, writer], list(tasks)).kickoff({"case": CASE})
    calls = collector.llm.calls + analyst.llm.calls + writer.llm.calls
    expected_prompt = sum(
        count_tokens(c.system + " ".join(m["content"] for m in c.messages)) for c in calls
    )
    assert out.token_usage["calls"] == 4
    assert out.token_usage["prompt_tokens"] == expected_prompt
    expected_completion = sum(count_tokens(t) for t in ["EV-1", "contest", "too many words in this reply", "ok"])
    assert out.token_usage["completion_tokens"] == expected_completion == 11
    assert out.token_usage["total_tokens"] == expected_prompt + expected_completion


@pytest.mark.parametrize("problem", ["no-agent", "foreign-agent", "forward-context", "duplicate", "hierarchical", "empty"])
def test_validate_rejects_broken_crews(problem):
    collector, analyst, writer = make_agents([], [], [])
    collect, assess, write = make_tasks(collector, analyst, writer)
    agents, tasks, process = [collector, analyst, writer], [collect, assess, write], Process.sequential
    if problem == "no-agent":
        assess.agent = None
    elif problem == "foreign-agent":
        agents = [collector, analyst]
    elif problem == "forward-context":
        assess.context = [write]
    elif problem == "duplicate":
        write.name = "collect"
    elif problem == "hierarchical":
        process = Process.hierarchical
    else:
        tasks = []
    with pytest.raises(ValueError):
        Crew(agents, tasks, process).kickoff({"case": CASE})
    assert collector.llm.calls == []  # nothing runs before the crew is valid
