import operator
from typing import Annotated, TypedDict

import pytest

from agents.mini_graph import (
    END,
    START,
    GraphError,
    GraphRecursionError,
    InvalidUpdateError,
    Overwrite,
    StateGraph,
    apply_update,
    channels,
)

pytestmark = pytest.mark.exercise


class State(TypedDict):
    status: str
    count: int
    log: Annotated[list[str], operator.add]


REDUCERS = {"status": None, "count": None, "log": operator.add}


def note(text, **extra):
    def node(state):
        return {"log": [text], **extra}

    return node


# --- state schema and reducers ---------------------------------------------------------------------------


def test_channels_reads_reducers_from_annotated():
    assert channels(State) == {"status": None, "count": None, "log": operator.add}


def test_channels_uses_last_callable_in_metadata():
    def keep_left(left, right):
        return left

    class S(TypedDict):
        x: Annotated[list, "a comment", keep_left]

    assert channels(S) == {"x": keep_left}


def test_apply_update_overwrites_without_reducer_and_appends_with_one():
    state = {"status": "new", "count": 1, "log": ["a"]}
    new = apply_update(state, {"status": "open", "log": ["b"]}, REDUCERS)
    assert new == {"status": "open", "count": 1, "log": ["a", "b"]}


def test_apply_update_returns_new_state_and_leaves_old_alone():
    state = {"status": "new", "log": ["a"]}
    apply_update(state, {"status": "open", "log": ["b"]}, REDUCERS)
    assert state == {"status": "new", "log": ["a"]}


def test_apply_update_first_write_to_reducer_key_stores_value():
    assert apply_update({}, {"log": ["a"]}, REDUCERS) == {"log": ["a"]}


def test_apply_update_empty_list_does_not_clear_but_overwrite_does():
    state = {"log": ["bad sql"]}
    assert apply_update(state, {"log": []}, REDUCERS)["log"] == ["bad sql"]
    assert apply_update(state, {"log": Overwrite([])}, REDUCERS)["log"] == []


def test_apply_update_rejects_unknown_key():
    with pytest.raises(InvalidUpdateError, match="node 'classify' wrote unknown key 'catgory'"):
        apply_update({}, {"catgory": "fraud"}, REDUCERS, node="classify")


def test_apply_update_rejects_non_dict():
    with pytest.raises(InvalidUpdateError, match="node 'review' returned NoneType, expected a dict of updates"):
        apply_update({}, None, REDUCERS, node="review")


# --- building and validating ------------------------------------------------------------------------------


def test_add_methods_chain_and_reject_reserved_and_duplicate_names():
    g = StateGraph(State)
    assert g.add_node("a", note("a")) is g
    assert g.add_edge(START, "a") is g
    with pytest.raises(GraphError):
        g.add_node(END, note("x"))
    with pytest.raises(GraphError):
        g.add_node("a", note("again"))
    with pytest.raises(GraphError):
        g.add_edge(END, "a")
    with pytest.raises(GraphError):
        g.add_edge("a", START)


def test_valid_graph_has_no_problems():
    g = StateGraph(State).add_node("a", note("a")).add_edge(START, "a").add_edge("a", END)
    assert g.validate() == []


def test_validate_reports_every_problem_in_order():
    g = StateGraph(State)
    g.add_node("a", note("a")).add_node("b", note("b")).add_node("c", note("c")).add_node("d", note("d"))
    g.add_edge("a", "b").add_edge("a", "c").add_edge("ghost", "a").add_edge("b", "nowhere")
    g.add_edge("b", END)
    g.add_conditional_edges("b", lambda s: "x", {"x": "missing"})
    assert g.validate() == [
        "no entry point: add an edge from START",
        "edge from unknown node 'ghost'",
        "edge to unknown node 'nowhere'",
        "path map of 'b' names unknown node 'missing'",
        "node 'a' has 2 static edges (fan-out is not supported)",
        "node 'b' has both a static edge and conditional edges",
        "node 'c' has no outgoing edge",
        "node 'd' has no outgoing edge",
        "node 'a' is unreachable from START",
        "node 'b' is unreachable from START",
        "node 'c' is unreachable from START",
        "node 'd' is unreachable from START",
    ]


def test_path_map_limits_reachability_but_bare_router_reaches_everything():
    def build(path_map):
        g = StateGraph(State)
        for name in ("a", "b", "orphan"):
            g.add_node(name, note(name))
        g.add_edge(START, "a")
        g.add_conditional_edges("a", lambda s: "b", path_map)
        g.add_edge("b", END).add_edge("orphan", END)
        return g

    assert build({"b": "b", "end": END}).validate() == ["node 'orphan' is unreachable from START"]
    assert build(None).validate() == []


def test_compile_raises_with_all_problems_joined():
    g = StateGraph(State).add_node("a", note("a"))
    with pytest.raises(GraphError) as info:
        g.compile()
    assert str(info.value) == (
        "no entry point: add an edge from START; node 'a' has no outgoing edge; node 'a' is unreachable from START"
    )


# --- running: edges, conditional edges, cycles ------------------------------------------------------------


def linear():
    g = StateGraph(State)
    g.add_node("open", note("open", status="open")).add_node("close", note("close", status="closed"))
    g.add_edge(START, "open").add_edge("open", "close").add_edge("close", END)
    return g.compile()


def test_invoke_runs_nodes_in_order_and_merges_updates():
    assert linear().invoke({"log": ["start"], "count": 0}) == {
        "log": ["start", "open", "close"],
        "count": 0,
        "status": "closed",
    }


def test_conditional_edge_uses_path_map():
    g = StateGraph(State)
    g.add_node("check", note("check")).add_node("refund", note("refund")).add_node("reply", note("reply"))
    g.add_edge(START, "check")
    g.add_conditional_edges("check", lambda s: "big" if s["count"] > 10 else "small", {"big": "reply", "small": "refund"})
    g.add_edge("refund", END).add_edge("reply", END)
    app = g.compile()
    assert app.invoke({"count": 50, "log": []})["log"] == ["check", "reply"]
    assert app.invoke({"count": 5, "log": []})["log"] == ["check", "refund"]


def test_router_returning_unmapped_value_raises():
    g = StateGraph(State).add_node("a", note("a")).add_edge(START, "a")
    g.add_conditional_edges("a", lambda s: "maybe", {"yes": END})
    with pytest.raises(GraphError, match="router of 'a' returned 'maybe', not in its path map"):
        g.compile().invoke({"log": []})


def test_router_without_map_returning_unknown_node_raises():
    g = StateGraph(State).add_node("a", note("a")).add_edge(START, "a")
    g.add_conditional_edges("a", lambda s: "b")
    with pytest.raises(GraphError, match="router of 'a' returned unknown node 'b'"):
        g.compile().invoke({"log": []})


def counter_loop(stop_at):
    g = StateGraph(State)
    g.add_node("work", lambda s: {"count": s["count"] + 1, "log": [f"work {s['count'] + 1}"]})
    g.add_edge(START, "work")
    g.add_conditional_edges("work", lambda s: END if s["count"] >= stop_at else "work")
    return g.compile()


def test_cycle_runs_until_router_returns_end():
    result = counter_loop(3).invoke({"count": 0, "log": []})
    assert result["count"] == 3
    assert result["log"] == ["work 1", "work 2", "work 3"]


def test_recursion_limit_counts_node_runs():
    assert counter_loop(3).invoke({"count": 0, "log": []}, recursion_limit=3)["count"] == 3
    with pytest.raises(GraphRecursionError, match="recursion limit of 2 reached without hitting END"):
        counter_loop(3).invoke({"count": 0, "log": []}, recursion_limit=2)


def test_endless_cycle_stops_at_limit():
    seen = []

    def work(state):
        seen.append(state["count"])
        return {"count": state["count"] + 1}

    g = StateGraph(State).add_node("work", work).add_edge(START, "work").add_edge("work", "work")
    with pytest.raises(GraphRecursionError):
        g.compile().invoke({"count": 0}, recursion_limit=5)
    assert seen == [0, 1, 2, 3, 4]


# --- streaming --------------------------------------------------------------------------------------------


def test_stream_updates_yields_node_and_update():
    chunks = list(linear().stream({"log": []}, stream_mode="updates"))
    assert chunks == [
        {"open": {"log": ["open"], "status": "open"}},
        {"close": {"log": ["close"], "status": "closed"}},
    ]


def test_stream_values_yields_input_then_full_state():
    chunks = list(linear().stream({"log": []}, stream_mode="values"))
    assert chunks == [
        {"log": []},
        {"log": ["open"], "status": "open"},
        {"log": ["open", "close"], "status": "closed"},
    ]


def test_node_mutating_state_has_no_effect():
    def sneaky(state):
        state["log"].append("mutated")
        state["status"] = "hacked"
        return {"count": 1}

    g = StateGraph(State).add_node("s", sneaky).add_edge(START, "s").add_edge("s", END)
    assert g.compile().invoke({"log": [], "status": "new"}) == {"log": [], "status": "new", "count": 1}


def test_node_forgetting_to_return_raises():
    g = StateGraph(State).add_node("forgot", lambda s: None).add_edge(START, "forgot").add_edge("forgot", END)
    with pytest.raises(InvalidUpdateError, match="node 'forgot' returned NoneType"):
        g.compile().invoke({"log": []})
