import pytest

from agents.mini_graph import GraphRecursionError
from agents.triage_graph import CLASSIFY_SYSTEM, DRAFT_SYSTEM, build_triage_graph, initial_state, review_draft
from llm_fake import ScriptedLLM

pytestmark = pytest.mark.exercise


def dispute(amount_minor=12_500, reason="I never received the headphones I ordered."):
    # Synthetic SandPay dispute.
    return {"id": "dp_1042", "amount_minor": amount_minor, "currency": "EUR", "reason": reason, "merchant_id": "mer_77"}


GOOD = "Dispute dp_1042: the parcel was delivered on 3 March with tracking TRK-88 signed by the cardholder."
NO_ID = "The parcel was delivered on 3 March with tracking TRK-88 signed by the cardholder."


# --- the review check -------------------------------------------------------------------------------------


def test_review_draft_passes_a_good_draft():
    assert review_draft(GOOD, dispute()) == []


def test_review_draft_lists_problems_in_order():
    long_text = "We guarantee a win. " + "word " * 60
    assert review_draft(long_text, dispute(), max_words=60) == [
        "missing dispute id dp_1042",
        "too long: 64 words (max 60)",
        "promises an outcome",
    ]


# --- routing ----------------------------------------------------------------------------------------------


def test_duplicate_low_amount_is_refunded_without_drafting():
    llm = ScriptedLLM(["duplicate"])
    result = build_triage_graph(llm).invoke(initial_state(dispute()))
    assert result["decision"] == "refund"
    assert result["log"] == ["classify: duplicate", "assess_risk: low", "auto_refund: refund"]
    assert len(llm.calls) == 1


def test_classify_request_is_exact():
    llm = ScriptedLLM(["duplicate"])
    build_triage_graph(llm).invoke(initial_state(dispute()))
    call = llm.calls[0]
    assert call.system == CLASSIFY_SYSTEM
    assert call.messages == [{"role": "user", "content": "Dispute dp_1042: I never received the headphones I ordered."}]
    assert call.temperature == 0.0
    assert call.max_tokens == 5


def test_fraud_is_escalated_whatever_the_amount():
    llm = ScriptedLLM([" FRAUD\n"])
    result = build_triage_graph(llm).invoke(initial_state(dispute(amount_minor=900)))
    assert result["category"] == "fraud"
    assert result["risk"] == "high"
    assert result["decision"] == "escalate"
    assert result["log"] == ["classify: fraud", "assess_risk: high", "escalate: escalate"]


def test_large_amount_is_escalated_even_when_duplicate():
    llm = ScriptedLLM(["duplicate"])
    result = build_triage_graph(llm, high_amount_minor=50_000).invoke(initial_state(dispute(amount_minor=50_000)))
    assert result["decision"] == "escalate"


def test_unknown_category_becomes_other_and_is_drafted():
    llm = ScriptedLLM(["Chargeback!", GOOD])
    result = build_triage_graph(llm).invoke(initial_state(dispute()))
    assert result["category"] == "other"
    assert result["decision"] == "respond"
    assert result["log"] == [
        "classify: other",
        "assess_risk: low",
        "draft_response: attempt 1",
        "review: ok",
        "finalize: respond",
    ]


# --- the review cycle -------------------------------------------------------------------------------------


def test_failed_review_loops_back_with_the_problems():
    llm = ScriptedLLM(["not_received", NO_ID, GOOD])
    result = build_triage_graph(llm).invoke(initial_state(dispute()))
    assert result["decision"] == "respond"
    assert result["drafts"] == 2
    assert result["draft"] == GOOD
    assert result["problems"] == []
    assert result["review_notes"] == ["attempt 1: missing dispute id dp_1042"]
    first, second = llm.calls[1], llm.calls[2]
    assert first.system == DRAFT_SYSTEM and second.system == DRAFT_SYSTEM
    assert "Fix these problems" not in first.messages[0]["content"]
    assert second.messages[0]["content"].endswith(
        "Fix these problems from the last review:\n- missing dispute id dp_1042"
    )
    assert "dp_1042" in first.messages[0]["content"] and "12500" in first.messages[0]["content"]


def test_gives_up_and_escalates_after_max_drafts():
    llm = ScriptedLLM(["not_received", NO_ID, NO_ID, NO_ID])
    result = build_triage_graph(llm, max_drafts=3).invoke(initial_state(dispute()))
    assert result["decision"] == "escalate"
    assert result["drafts"] == 3
    assert result["review_notes"] == [f"attempt {n}: missing dispute id dp_1042" for n in (1, 2, 3)]
    assert result["log"][-3:] == ["draft_response: attempt 3", "review: 1 problem(s)", "escalate: escalate"]
    assert len(llm.calls) == 4


def test_recursion_limit_stops_a_loop_that_would_run_too_long():
    llm = ScriptedLLM(lambda request: "not_received" if request.system == CLASSIFY_SYSTEM else NO_ID)
    app = build_triage_graph(llm, max_drafts=10)
    with pytest.raises(GraphRecursionError):
        app.invoke(initial_state(dispute()), recursion_limit=8)
    assert len(llm.calls) == 4  # classify + 3 drafts in 8 node runs


def test_stream_shows_each_node_once_per_run():
    llm = ScriptedLLM(["not_received", NO_ID, GOOD])
    names = [next(iter(chunk)) for chunk in build_triage_graph(llm).stream(initial_state(dispute()))]
    assert names == [
        "classify",
        "assess_risk",
        "draft_response",
        "review",
        "draft_response",
        "review",
        "finalize",
    ]
