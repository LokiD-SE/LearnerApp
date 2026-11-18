import pytest
from agents.checkpoint_runner import END, CheckpointRunner, EmptyThreadError, SqliteCheckpointer

pytestmark = pytest.mark.exercise


class Crash(Exception):
    pass


def make_graph(checkpointer, ran, crash_in=None):
    """load_payment -> assess -> (refund_draft | escalate) -> END, recording every node call in ``ran``."""

    def load_payment(state):
        ran.append("load_payment")
        return {"amount_minor": 4999, "merchant": "Lumen Books"}

    def assess(state):
        ran.append("assess")
        if crash_in == "assess" and ran.count("assess") == 1:
            raise Crash("worker killed")
        return {"risk": "high" if state["amount_minor"] > 3000 else "low"}

    def refund_draft(state):
        ran.append("refund_draft")
        return {"draft": f"refund {state['amount_minor']} to {state['payment_id']}"}

    def escalate(state):
        ran.append("escalate")
        return {"draft": "escalated to a human"}

    return CheckpointRunner(
        nodes={"load_payment": load_payment, "assess": assess, "refund_draft": refund_draft, "escalate": escalate},
        edges={
            "load_payment": "assess",
            "assess": lambda s: "escalate" if s["risk"] == "high" else "refund_draft",
            "refund_draft": END,
            "escalate": END,
        },
        entry="load_payment",
        checkpointer=checkpointer,
    )


CFG = {"configurable": {"thread_id": "case-7"}}


def test_one_checkpoint_for_the_input_and_one_per_node():
    ran = []
    runner = make_graph(SqliteCheckpointer(), ran)
    final = runner.invoke({"payment_id": "pay_1001"}, CFG)
    assert final == {
        "payment_id": "pay_1001", "amount_minor": 4999, "merchant": "Lumen Books", "risk": "high",
        "draft": "escalated to a human",
    }
    history = runner.get_state_history(CFG)
    assert [c.checkpoint_id for c in history] == ["0004", "0003", "0002", "0001"]  # newest first
    assert [c.next for c in history] == [None, "escalate", "assess", "load_payment"]
    assert [c.source for c in history] == ["loop", "loop", "loop", "input"]
    assert [c.step for c in history] == [3, 2, 1, 0]
    assert [c.parent_id for c in history] == ["0003", "0002", "0001", None]
    assert history[2].values == {"payment_id": "pay_1001", "amount_minor": 4999, "merchant": "Lumen Books"}
    assert runner.get_state(CFG).checkpoint_id == "0004"


def test_threads_are_separate():
    runner = make_graph(SqliteCheckpointer(), [])
    runner.invoke({"payment_id": "pay_1"}, {"configurable": {"thread_id": "a"}})
    assert runner.get_state_history({"configurable": {"thread_id": "b"}}) == []
    assert runner.get_state({"configurable": {"thread_id": "b"}}) is None
    with pytest.raises(EmptyThreadError):
        runner.invoke(None, {"configurable": {"thread_id": "b"}})
    with pytest.raises(ValueError):
        runner.invoke({"x": 1}, {"configurable": {}})


def test_saved_checkpoints_cannot_be_changed_by_a_node():
    def sloppy(state):
        state["tags"].append("seen")  # mutates its argument
        return {"tags": state["tags"]}

    runner = CheckpointRunner({"sloppy": sloppy}, {}, "sloppy", SqliteCheckpointer())
    runner.invoke({"tags": []}, CFG)
    assert [c.values["tags"] for c in runner.get_state_history(CFG)] == [["seen"], []]
    with pytest.raises(TypeError):
        runner.invoke({"when": object()}, {"configurable": {"thread_id": "bad"}})


def test_resume_after_a_crash_runs_only_unfinished_nodes(tmp_path):
    path = str(tmp_path / "checkpoints.db")
    ran = []
    first = make_graph(SqliteCheckpointer(path), ran, crash_in="assess")
    with pytest.raises(Crash):
        first.invoke({"payment_id": "pay_1001"}, CFG)
    first.checkpointer.close()  # the process is gone; only the file remains

    restarted = make_graph(SqliteCheckpointer(path), ran, crash_in="assess")
    assert restarted.get_state(CFG).next == "assess"
    final = restarted.invoke(None, CFG)
    assert final["draft"] == "escalated to a human"
    assert ran == ["load_payment", "assess", "assess", "escalate"]  # load_payment did not run again
    assert len(restarted.get_state_history(CFG)) == 4


def test_resuming_a_finished_thread_runs_nothing():
    ran = []
    runner = make_graph(SqliteCheckpointer(), ran)
    final = runner.invoke({"payment_id": "pay_1001"}, CFG)
    assert runner.invoke(None, CFG) == final
    assert len(ran) == 3 and len(runner.get_state_history(CFG)) == 4


def test_new_input_on_an_existing_thread_keeps_its_values():
    ran = []
    runner = make_graph(SqliteCheckpointer(), ran)
    runner.invoke({"payment_id": "pay_1001"}, CFG)
    second = runner.invoke({"note": "customer called again"}, CFG)
    assert second["payment_id"] == "pay_1001" and second["note"] == "customer called again"
    newest_input = [c for c in runner.get_state_history(CFG) if c.source == "input"][0]
    assert newest_input.checkpoint_id == "0005" and newest_input.parent_id == "0004" and newest_input.step == 4


def test_replay_reruns_only_nodes_after_the_checkpoint():
    ran = []
    runner = make_graph(SqliteCheckpointer(), ran)
    runner.invoke({"payment_id": "pay_1001"}, CFG)
    before_assess = next(c for c in runner.get_state_history(CFG) if c.next == "assess")
    ran.clear()
    runner.invoke(None, before_assess.config)
    assert ran == ["assess", "escalate"]
    history = runner.get_state_history(CFG)
    assert len(history) == 6
    assert history[1].parent_id == before_assess.checkpoint_id  # the replay branches off the old checkpoint


def test_fork_changes_the_path_and_keeps_the_original():
    ran = []
    runner = make_graph(SqliteCheckpointer(), ran)
    original = runner.invoke({"payment_id": "pay_1001"}, CFG)
    before_assess = next(c for c in runner.get_state_history(CFG) if c.next == "assess")
    ran.clear()
    fork_config = runner.update_state(before_assess.config, {"amount_minor": 1200})
    fork = runner.get_state(fork_config)
    assert fork.source == "update" and fork.parent_id == before_assess.checkpoint_id and fork.next == "assess"
    assert fork.values["amount_minor"] == 1200 and fork.values["merchant"] == "Lumen Books"
    result = runner.invoke(None, fork_config)
    assert ran == ["assess", "refund_draft"]
    assert result["draft"] == "refund 1200 to pay_1001"
    assert runner.get_state(before_assess.config).values["amount_minor"] == 4999  # history untouched
    assert runner.get_state({"configurable": {"thread_id": "case-7", "checkpoint_id": "0004"}}).values == original
    with pytest.raises(EmptyThreadError):
        runner.update_state({"configurable": {"thread_id": "case-7", "checkpoint_id": "9999"}}, {})
