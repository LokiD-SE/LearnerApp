"""EXERCISE - implement channels, apply_update (fix the draft), validate, _next and stream.

A mini state graph in plain Python - the core ideas of LangGraph's ``StateGraph``, small enough to read.

    class State(TypedDict):
        dispute_id: str
        status: str                              # no reducer: an update overwrites
        log: Annotated[list[str], operator.add]  # reducer: an update is appended

    graph = StateGraph(State)
    graph.add_node("classify", classify)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", route, {"refund": "refund", "done": END})
    graph.add_edge("refund", END)
    app = graph.compile()          # validates the structure, raises GraphError
    app.invoke({"dispute_id": "dp_1", "log": []}, recursion_limit=10)
    for chunk in app.stream({...}, stream_mode="updates"): ...

Names follow LangGraph's (``StateGraph``, ``START``, ``END``, ``add_node``, ``add_edge``,
``add_conditional_edges``, ``compile``, ``invoke``, ``stream``, ``Overwrite``, ``GraphRecursionError``,
``InvalidUpdateError``) so the mapping is easy, but this is NOT LangGraph: it runs one node at a time (no
parallel super-steps), has no checkpointer, and its validation rules are its own (stricter in places).
"""

from __future__ import annotations

import copy
import typing
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

START = "__start__"
END = "__end__"


class GraphError(Exception):
    """The graph is built wrong (unknown node, no entry point, unreachable node...)."""


class InvalidUpdateError(Exception):
    """A node returned something that cannot be applied to the state."""


class GraphRecursionError(Exception):
    """The run used ``recursion_limit`` node steps without reaching END."""


@dataclass(frozen=True)
class Overwrite:
    """Wrap an update value to bypass the key's reducer and replace the value (e.g. clear a list)."""

    value: Any


def channels(schema: type) -> dict[str, Callable[[Any, Any], Any] | None]:
    """Return ``{key: reducer or None}`` for a TypedDict state schema.

    A key annotated ``Annotated[T, fn]`` has reducer ``fn`` (the last callable in the metadata);
    any other key has ``None`` (overwrite). Keys keep the schema's order.
    """
    raise NotImplementedError


def apply_update(
    state: dict[str, Any],
    update: Any,
    reducers: dict[str, Callable[[Any, Any], Any] | None],
    node: str = "?",
) -> dict[str, Any]:
    """Return a NEW state with ``update`` merged in; ``state`` is not changed.

    - ``update`` must be a dict, else InvalidUpdateError naming the node and the type it returned.
    - Every key must be in ``reducers`` (the schema), else InvalidUpdateError naming node and key.
    - No reducer: the value replaces the old one.
    - A reducer: ``reducer(old, new)``; when the key has no value yet, the new value is stored as is.
    - ``Overwrite(v)``: store ``v`` as is, even when the key has a reducer.
    """
    # Teammate's draft: it ignores reducers, unknown keys and non-dict updates, and changes ``state`` in place.
    for key, value in update.items():
        state[key] = value
    return state


class StateGraph:
    """Builder: add nodes and edges, then ``compile()``. Every ``add_*`` returns ``self`` for chaining."""

    def __init__(self, schema: type):
        self.schema = schema
        self.reducers = channels(schema)
        self.nodes: dict[str, Callable[[dict[str, Any]], Any]] = {}
        self.edges: list[tuple[str, str]] = []
        # source -> (router, path_map or None)
        self.branches: dict[str, tuple[Callable[[dict[str, Any]], str], dict[str, str] | None]] = {}

    def add_node(self, name: str, fn: Callable[[dict[str, Any]], Any]) -> StateGraph:
        """Register a node. GraphError if the name is START, END or already used."""
        if name in (START, END):
            raise GraphError(f"'{name}' is reserved")
        if name in self.nodes:
            raise GraphError(f"node '{name}' already exists")
        self.nodes[name] = fn
        return self

    def add_edge(self, source: str, target: str) -> StateGraph:
        """Always go from ``source`` to ``target``. GraphError if source is END or target is START."""
        if source == END:
            raise GraphError("END cannot be the source of an edge")
        if target == START:
            raise GraphError("START cannot be the target of an edge")
        self.edges.append((source, target))
        return self

    def add_conditional_edges(
        self,
        source: str,
        router: Callable[[dict[str, Any]], str],
        path_map: dict[str, str] | None = None,
    ) -> StateGraph:
        """After ``source`` runs, call ``router(state)`` to pick the next node.

        With ``path_map`` the router's return value is looked up in it; without, the value is the node name.
        GraphError if source is END or ``source`` already has conditional edges.
        """
        if source == END:
            raise GraphError("END cannot be the source of an edge")
        if source in self.branches:
            raise GraphError(f"node '{source}' already has conditional edges")
        self.branches[source] = (router, dict(path_map) if path_map is not None else None)
        return self

    def validate(self) -> list[str]:
        """Return every structural problem as a message (empty list = valid). Messages, in this order:

        - ``"no entry point: add an edge from START"``
        - ``"edge from unknown node 'x'"`` / ``"edge to unknown node 'x'"`` (also for conditional sources)
        - ``"path map of 'x' names unknown node 'y'"``
        - ``"node 'x' has both a static edge and conditional edges"``
        - ``"node 'x' has 2 static edges (fan-out is not supported)"``
        - ``"node 'x' has no outgoing edge"``
        - ``"node 'x' is unreachable from START"``

        Reachability follows static edges and path maps. A router WITHOUT a path map may return any node,
        so it is treated as reaching every node (which is why path maps let compile check more).
        """
        raise NotImplementedError

    def _successors(self, name: str) -> set[str]:
        result = {t for s, t in self.edges if s == name}
        if name in self.branches:
            _, path_map = self.branches[name]
            result |= set(path_map.values()) if path_map is not None else set(self.nodes)
        return result

    def _reachable(self) -> set[str]:
        seen: set[str] = set()
        todo = [START]
        while todo:
            for nxt in self._successors(todo.pop()):
                if nxt not in seen and nxt in self.nodes:
                    seen.add(nxt)
                    todo.append(nxt)
        return seen

    def compile(self) -> CompiledGraph:
        """Validate, then freeze. GraphError listing every problem (joined with "; ") if invalid."""
        problems = self.validate()
        if problems:
            raise GraphError("; ".join(problems))
        return CompiledGraph(
            dict(self.nodes),
            dict(self.reducers),
            {s: t for s, t in self.edges},
            dict(self.branches),
        )


class CompiledGraph:
    """A validated graph you can ``invoke`` or ``stream``."""

    def __init__(self, nodes, reducers, edges, branches):
        self.nodes = nodes
        self.reducers = reducers
        self.edges = edges
        self.branches = branches

    def _next(self, source: str, state: dict[str, Any]) -> str:
        """The node after ``source``: its static edge's target, or the router's choice.

        The router gets a deep copy of the state. With a path map, look the choice up in it (GraphError
        ``"router of '<source>' returned '<choice>', not in its path map"`` if missing). The result must be END
        or a node, else GraphError ``"router of '<source>' returned unknown node '<choice>'"``.
        """
        raise NotImplementedError

    def stream(
        self,
        inputs: dict[str, Any],
        *,
        recursion_limit: int = 25,
        stream_mode: str = "updates",
    ) -> Iterator[dict[str, Any]]:
        """Run the graph, yielding after every node.

        - ``"updates"``: ``{node_name: update}`` after each node (the update as returned).
        - ``"values"``: a copy of the whole state - first the input state, then after each node.
        Each node gets a deep copy of the state, so mutating it has no effect: return updates instead.
        Raises GraphRecursionError when ``recursion_limit`` nodes have run and the next step is not END.
        """
        raise NotImplementedError
        yield {}  # keeps this a generator

    def invoke(self, inputs: dict[str, Any], *, recursion_limit: int = 25) -> dict[str, Any]:
        """Run to END and return the final state."""
        state: dict[str, Any] = {}
        for state in self.stream(inputs, recursion_limit=recursion_limit, stream_mode="values"):
            pass
        return state
