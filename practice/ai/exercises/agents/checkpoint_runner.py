"""A tiny checkpointed graph runner: per-step snapshots keyed by thread id, resume after a crash, replay and fork.

It is a plain-Python model of what a LangGraph checkpointer does (LangGraph is not installed here):

- ``SqliteCheckpointer`` stores one row per step - a *checkpoint* - keyed by ``(thread_id, checkpoint_id)``, with
  the state as JSON, the node to run next and the parent checkpoint. It uses the standard library's ``sqlite3``,
  so a file path survives the process that wrote it (``":memory:"`` does not).
- ``CheckpointRunner`` runs nodes (``fn(state) -> partial update``) along edges, saving a checkpoint after the
  input and after every node. Its config mirrors LangGraph's: ``{"configurable": {"thread_id": ...}}``, with an
  optional ``"checkpoint_id"``.

    runner.invoke({"payment_id": "pay_1001"}, config)   # new input: start at the entry node
    runner.invoke(None, config)                         # continue unfinished work (after a crash)
    runner.invoke(None, older.config)                   # replay from an older checkpoint
    fork = runner.update_state(older.config, {...})     # fork: a new checkpoint with edited values
    runner.invoke(None, fork)

Differences from LangGraph, on purpose: one node per step (no parallel super-steps), updates overwrite keys
(no reducers), checkpoint ids are zero-padded counters per thread instead of time-ordered UUIDs.
"""

from __future__ import annotations

import copy
import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Callable

END = "__end__"

Node = Callable[[dict[str, Any]], dict[str, Any]]
Edge = str | Callable[[dict[str, Any]], str]


class EmptyThreadError(Exception):
    """``invoke(None, config)`` on a thread (or checkpoint id) that has no checkpoint to continue from."""


@dataclass(frozen=True)
class Checkpoint:
    """One saved step of a thread. ``next`` is the node to run next, or ``None`` when the run has finished."""

    thread_id: str
    checkpoint_id: str
    parent_id: str | None
    step: int
    source: str  # "input" | "loop" | "update"
    next: str | None
    values: dict[str, Any]

    @property
    def config(self) -> dict[str, Any]:
        """The config that points at exactly this checkpoint - pass it to ``invoke`` to replay from here."""
        return {"configurable": {"thread_id": self.thread_id, "checkpoint_id": self.checkpoint_id}}


class SqliteCheckpointer:
    """Saves checkpoints in SQLite. Values are stored as JSON, so a saved checkpoint can never change later."""

    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS checkpoints ("
            " thread_id TEXT NOT NULL, checkpoint_id TEXT NOT NULL, parent_id TEXT, step INTEGER NOT NULL,"
            " source TEXT NOT NULL, next TEXT, values_json TEXT NOT NULL,"
            " PRIMARY KEY (thread_id, checkpoint_id))"
        )
        self.db.commit()

    def put(
        self,
        thread_id: str,
        parent_id: str | None,
        step: int,
        source: str,
        next: str | None,
        values: dict[str, Any],
    ) -> Checkpoint:
        """Saves a new checkpoint and returns it. Ids count up per thread: "0001", "0002", ...

        The row is committed before ``put`` returns, so a crash afterwards cannot lose it. Values that JSON
        cannot encode raise ``TypeError`` - state must be serialisable to be saved.
        """
        raise NotImplementedError

    def get(self, thread_id: str, checkpoint_id: str | None = None) -> Checkpoint | None:
        """That checkpoint, or the thread's latest when ``checkpoint_id`` is None; None if there is none."""
        raise NotImplementedError

    def list(self, thread_id: str) -> list[Checkpoint]:
        """Every checkpoint of the thread, newest first (like LangGraph's ``get_state_history``)."""
        raise NotImplementedError

    def close(self) -> None:
        self.db.close()


def _row_to_checkpoint(row: tuple) -> Checkpoint:
    thread_id, checkpoint_id, parent_id, step, source, next_node, values_json = row
    return Checkpoint(thread_id, checkpoint_id, parent_id, step, source, next_node, json.loads(values_json))


def _thread_of(config: dict[str, Any]) -> tuple[str, str | None]:
    configurable = config.get("configurable", {})
    if "thread_id" not in configurable:
        raise ValueError('config needs {"configurable": {"thread_id": ...}}')
    return configurable["thread_id"], configurable.get("checkpoint_id")


class CheckpointRunner:
    """Runs a graph of nodes and saves a checkpoint after the input and after every node."""

    def __init__(self, nodes: dict[str, Node], edges: dict[str, Edge], entry: str, checkpointer: SqliteCheckpointer):
        if entry not in nodes:
            raise ValueError(f"unknown entry node {entry!r}")
        self.nodes = nodes
        self.edges = edges
        self.entry = entry
        self.checkpointer = checkpointer

    def _route(self, node: str, values: dict[str, Any]) -> str | None:
        edge = self.edges.get(node, END)
        target = edge(values) if callable(edge) else edge
        if target == END:
            return None
        if target not in self.nodes:
            raise ValueError(f"edge from {node!r} leads to unknown node {target!r}")
        return target

    def invoke(self, input: dict[str, Any] | None, config: dict[str, Any]) -> dict[str, Any]:
        """Runs the thread and returns its final values.

        - ``input`` is a dict: merge it into the thread's latest values (empty for a new thread), save an
          ``"input"`` checkpoint whose ``next`` is the entry node, and run from there.
        - ``input`` is None: continue from the checkpoint named in the config, or the latest one. Nodes before it
          are not run again. A finished checkpoint (``next is None``) returns its values without running
          anything. No checkpoint at all -> ``EmptyThreadError``.

        Each node receives a deep copy of the values, so a node that mutates its argument cannot change a saved
        checkpoint. After each node: values = old values updated with the node's dict, route along the node's
        edge, save a ``"loop"`` checkpoint whose parent is the previous one. An exception in a node propagates
        and saves nothing for that node, so the latest checkpoint still names it as ``next``.
        """
        raise NotImplementedError

    def get_state(self, config: dict[str, Any]) -> Checkpoint | None:
        thread_id, checkpoint_id = _thread_of(config)
        return self.checkpointer.get(thread_id, checkpoint_id)

    def get_state_history(self, config: dict[str, Any]) -> list[Checkpoint]:
        thread_id, _ = _thread_of(config)
        return self.checkpointer.list(thread_id)

    def update_state(self, config: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
        """Forks: saves a new ``"update"`` checkpoint whose parent is the given one (or the latest), with
        ``values`` merged in and the same ``next``. The original checkpoint is not changed. Returns the new
        checkpoint's config; ``invoke(None, that_config)`` continues the fork.
        """
        raise NotImplementedError
