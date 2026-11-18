import pytest
from agents.approval_flow import (
    END,
    ApprovalRunner,
    Command,
    Context,
    NoPendingInterrupt,
    SandPayGateway,
    build_refund_graph,
    refund_key,
)
from llm_fake import ScriptedLLM

pytestmark = pytest.mark.exercise

PROPOSAL = {"tool": "propose_refund", "input": {"payment_id": "pay_2001", "amount_minor": 4999, "reason": "duplicate charge"}}
CASE = {"case_id": "case-42", "message": "I was charged twice for order 7781."}


def setup(script=None):
    llm = ScriptedLLM(script or [PROPOSAL])
    gateway = SandPayGateway({"pay_2001": 4999})
    return llm, gateway, build_refund_graph(llm, gateway)


def test_pauses_before_the_refund_with_a_review_payload():
    llm, gateway, runner = setup()
    result = runner.invoke(CASE, "t1")
    assert result["__interrupt__"] == [{
        "question": "Approve this SandPay refund?", "case_id": "case-42", "payment_id": "pay_2001",
        "amount_minor": 4999, "captured_minor": 4999, "reason": "duplicate charge", "error": None,
    }]
    assert gateway.calls == 0  # nothing irreversible happened yet
    paused = runner.get_state("t1")
    assert paused["next"] == "human_review" and paused["interrupt"]["case_id"] == "case-42"
    assert llm.calls[0].tools[0]["name"] == "propose_refund"


def test_approve_issues_exactly_one_refund():
    llm, gateway, runner = setup()
    runner.invoke(CASE, "t1")
    final = runner.invoke(Command(resume={"action": "approve"}), "t1")
    assert "__interrupt__" not in final
    assert final["status"] == "refunded"
    assert final["refund"] == {"refund_id": "re_001", "payment_id": "pay_2001", "amount_minor": 4999}
    assert len(gateway.refunds) == 1 and len(llm.calls) == 1  # the draft node did not run again
    assert runner.get_state("t1")["next"] is None


def test_edit_changes_the_amount_and_invalid_edits_ask_again():
    _, gateway, runner = setup()
    runner.invoke(CASE, "t1")
    again = runner.invoke(Command(resume={"action": "edit", "amount_minor": 9000}), "t1")
    assert again["__interrupt__"][0]["error"] == "amount_minor must be an integer from 1 to 4999"
    assert gateway.calls == 0
    again = runner.invoke(Command(resume={"action": "edit", "amount_minor": "2500"}), "t1")
    assert again["__interrupt__"][0]["error"].startswith("amount_minor must be an integer")
    again = runner.invoke(Command(resume="yes please"), "t1")
    assert again["__interrupt__"][0]["error"] == "action must be approve, edit or reject"
    final = runner.invoke(Command(resume={"action": "edit", "amount_minor": 2500}), "t1")
    assert final["status"] == "refunded" and final["edited_by_human"] is True
    assert gateway.refunds == [{"refund_id": "re_001", "payment_id": "pay_2001", "amount_minor": 2500}]


def test_reject_issues_no_refund():
    _, gateway, runner = setup()
    runner.invoke(CASE, "t1")
    final = runner.invoke(Command(resume={"action": "reject", "note": "already refunded by bank"}), "t1")
    assert final["status"] == "rejected" and final["reject_note"] == "already refunded by bank"
    assert gateway.calls == 0


def test_resume_needs_a_paused_thread():
    _, _, runner = setup()
    with pytest.raises(NoPendingInterrupt):
        runner.invoke(Command(resume={"action": "approve"}), "never-started")
    runner.invoke(CASE, "t1")
    runner.invoke(Command(resume={"action": "approve"}), "t1")
    with pytest.raises(NoPendingInterrupt):
        runner.invoke(Command(resume={"action": "approve"}), "t1")  # already finished
    with pytest.raises(NoPendingInterrupt):
        runner.invoke(Command(resume={"action": "approve"}), "t2")  # another thread


def test_no_tool_call_means_no_review():
    _, gateway, runner = setup(["Please send us the order number."])
    final = runner.invoke(CASE, "t1")
    assert final["status"] == "no_refund_proposed" and "__interrupt__" not in final and gateway.calls == 0


def test_the_resumed_node_restarts_from_its_first_line():
    calls = []

    def ask(state, ctx):
        calls.append("before")
        answer = ctx.interrupt("name?")
        calls.append(f"after:{answer}")
        return {"name": answer}

    runner = ApprovalRunner({"ask": ask}, {"ask": END}, "ask")
    assert runner.invoke({}, "x")["__interrupt__"] == ["name?"]
    assert runner.invoke(Command(resume="Ada"), "x") == {"name": "Ada"}
    assert calls == ["before", "before", "after:Ada"]
    assert Context("v").interrupt("q") == "v"


def test_replaying_the_refund_step_does_not_refund_twice():
    _, gateway, runner = setup()
    runner.invoke(CASE, "t1")
    runner.invoke(Command(resume={"action": "approve"}), "t1")
    before_refund = next(c for c in runner.get_state_history("t1") if c["next"] == "issue_refund")
    replayed = runner.invoke(None, "t1", checkpoint_id=before_refund["checkpoint_id"])
    assert gateway.calls == 2 and len(gateway.refunds) == 1
    assert replayed["refund"]["refund_id"] == "re_001"
    assert refund_key({"case_id": "case-42", "amount_minor": 1}) == refund_key({"case_id": "case-42", "amount_minor": 2})


def test_lost_acknowledgement_then_retry_is_safe():
    _, gateway, runner = setup()
    runner.invoke(CASE, "t1")
    gateway.lose_next_ack = True
    with pytest.raises(ConnectionError):
        runner.invoke(Command(resume={"action": "approve"}), "t1")
    assert len(gateway.refunds) == 1  # it did happen
    assert runner.get_state("t1")["next"] == "issue_refund"  # but the graph never recorded it
    final = runner.invoke(None, "t1")
    assert final["refund"]["refund_id"] == "re_001" and len(gateway.refunds) == 1


def test_replay_from_before_review_asks_the_human_again():
    _, gateway, runner = setup()
    runner.invoke(CASE, "t1")
    runner.invoke(Command(resume={"action": "approve"}), "t1")
    before_review = [c for c in runner.get_state_history("t1") if c["next"] == "human_review"][-1]
    assert before_review["interrupt"] is None
    again = runner.invoke(None, "t1", checkpoint_id=before_review["checkpoint_id"])
    assert again["__interrupt__"][0]["amount_minor"] == 4999 and gateway.calls == 1
