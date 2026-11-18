"""Checks exercises/agents/workflow_patterns.py - lesson agent-loops-and-workflow-patterns.

ScriptedLLM plays the model. Parallel tests use a script that decides from the request (not from call order), so
they hold whether map_fn runs the calls on threads or one by one.
"""

import pytest

from agents.workflow_patterns import GateError, chain, classify, parallel_sections, route, thread_map, vote
from llm_fake import ScriptedLLM

pytestmark = pytest.mark.exercise


def last_prompt(llm):
    return llm.calls[-1].messages[-1]["content"]


def test_chain_feeds_each_output_into_the_next_prompt():
    llm = ScriptedLLM(["facts: po_1042, 80.00 refund", "Dear merchant, ...", "Cher marchand, ..."])
    out = chain(llm, ["Extract: {input}", "Draft a reply from {input}", "Translate to French: {input}"], "email text")
    assert out == ["facts: po_1042, 80.00 refund", "Dear merchant, ...", "Cher marchand, ..."]
    assert [c.messages[0]["content"] for c in llm.calls] == [
        "Extract: email text",
        "Draft a reply from facts: po_1042, 80.00 refund",
        "Translate to French: Dear merchant, ...",
    ]


def test_chain_gate_stops_the_chain():
    llm = ScriptedLLM(["facts: none found", "should not be called"])
    with pytest.raises(GateError) as info:
        chain(llm, ["Extract: {input}", "Draft: {input}"], "x", gate=lambda i, out: "po_" in out)
    assert info.value.step == 0 and info.value.output == "facts: none found"
    assert len(llm.calls) == 1


def test_classify_normalises_and_rejects_unknown_labels():
    labels = ["refund", "payout", "technical"]
    llm = ScriptedLLM([" Refund.\n", "chargeback", "payout"])
    assert classify(llm, "Please refund pay_1", labels) == "refund"
    assert classify(llm, "x", labels) is None
    assert classify(llm, "y", labels) == "payout"
    first = llm.calls[0]
    assert first.temperature == 0.0
    assert first.messages[0]["content"] == (
        "Classify the message into exactly one of: refund, payout, technical. Reply with the label only.\n"
        "<message>\nPlease refund pay_1\n</message>"
    )


def test_route_uses_the_handler_prompt():
    handlers = {"refund": "Refund policy answer for: {input}", "payout": "Payout answer for: {input}"}
    llm = ScriptedLLM(["payout", "Payouts arrive in 2 days."])
    assert route(llm, "When is my payout?", handlers) == ("payout", "Payouts arrive in 2 days.")
    assert last_prompt(llm) == "Payout answer for: When is my payout?"


def test_route_falls_back_without_a_second_call():
    llm = ScriptedLLM(["I think this is about a refund or a payout"])
    assert route(llm, "??", {"refund": "{input}", "payout": "{input}"}) == ("human", None)
    assert len(llm.calls) == 1


def by_prompt(req):
    prompt = req.messages[-1]["content"]
    return "SAFE" if prompt.startswith("Screen") else f"answer to {prompt.split(': ', 1)[1]}"


def test_parallel_sections_runs_every_prompt_and_keeps_names():
    llm = ScriptedLLM(by_prompt)
    prompts = {"answer": "Answer: {input}", "screen": "Screen: {input}"}
    seen = []

    def recording_map(fn, items):
        items = list(items)
        seen.append(items)
        return [fn(i) for i in items]

    out = parallel_sections(llm, "my payout?", prompts, map_fn=recording_map)
    assert out == {"answer": "answer to my payout?", "screen": "SAFE"}
    assert list(out) == ["answer", "screen"]
    assert seen == [["answer", "screen"]]


def test_parallel_sections_default_runs_on_threads():
    llm = ScriptedLLM(by_prompt)
    out = parallel_sections(llm, "q", {"a": "Answer: {input}", "s": "Screen: {input}", "b": "Answer: {input}"})
    assert out == {"a": "answer to q", "s": "SAFE", "b": "answer to q"}
    assert len(llm.calls) == 3


def test_thread_map_keeps_order():
    assert thread_map(lambda x: x * 2, [3, 1, 2]) == [6, 2, 4]
    assert thread_map(lambda x: x, []) == []


def sequential(fn, items):
    return [fn(i) for i in items]


def test_vote_majority_wins_and_uses_temperature():
    llm = ScriptedLLM(["fraud", "ok", "Fraud.", "fraud", "maybe?"])
    result = vote(llm, "Is this payment fraud?", ["fraud", "ok"], n=5, map_fn=sequential)
    assert result == {"label": "fraud", "votes": {"fraud": 3, "ok": 1, "invalid": 1}, "n": 5}
    assert all(c.temperature == 1.0 for c in llm.calls) and len(llm.calls) == 5
    assert all(c.messages[0]["content"] == "Is this payment fraud?" for c in llm.calls)


def test_vote_without_strict_majority_escalates():
    llm = ScriptedLLM(["fraud", "ok", "fraud", "ok", "unsure"])
    assert vote(llm, "p", ["fraud", "ok"], n=5, map_fn=sequential)["label"] is None
    llm = ScriptedLLM(["fraud", "fraud", "ok", "ok"])
    assert vote(llm, "p", ["fraud", "ok"], n=4, map_fn=sequential)["label"] is None
