"""Human approval before a risky SandPay refund: interrupt, resume with a decision, and replay-safe side effects.

A plain-Python model of LangGraph's ``interrupt()`` and ``Command(resume=...)`` (LangGraph is not installed here):

- A node calls ``ctx.interrupt(payload)``. The first time, that raises ``GraphInterrupt``; the runner saves a
  checkpoint that remembers the payload and returns ``{..., "__interrupt__": [payload]}`` to the caller.
- The caller resumes with ``runner.invoke(Command(resume=decision), thread_id)``. The interrupted node runs again
  **from its first line**, and this time ``ctx.interrupt(...)`` returns ``decision``.
- The refund itself goes to ``SandPayGateway`` - a fake of an external payment API that deduplicates by
  idempotency key - so replaying the graph or retrying after a lost acknowledgement cannot refund twice.

SandPay is fictional; amounts are integers in minor units (1999 = 19.99 EUR).
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from typing import Any, Callable

END = "__end__"

PROPOSE_REFUND_TOOL = {
    "name": "propose_refund",
    "description": "Propose a refund of a captured SandPay payment. A human approves it before it is issued.",
    "input_schema": {
        "type": "object",
        "properties": {
            "payment_id": {"type": "string"},
            "amount_minor": {"type": "integer", "minimum": 1},
            "reason": {"type": "string"},
        },
        "required": ["payment_id", "amount_minor", "reason"],
    },
}


# --- given: the interrupt mechanics' small types ------------------------------------------------------------


@dataclass(frozen=True)
class Command:
    """Resume a paused thread: ``resume`` becomes the return value of the pending ``interrupt()``."""

    resume: Any


class GraphInterrupt(Exception):
    """Raised by ``Context.interrupt`` to pause the run. Only the runner should catch it."""

    def __init__(self, payload: Any):
        super().__init__("graph interrupted for human input")
        self.payload = payload


class NoPendingInterrupt(Exception):
    """``Command(resume=...)`` sent to a thread that is not waiting for input."""


_NOTHING = object()


class Context:
    """Passed to each node. ``interrupt`` returns the resume value if there is one, otherwise pauses the run."""

    def __init__(self, resume: Any = _NOTHING):
        self._resume = resume

    def interrupt(self, payload: Any) -> Any:
        if self._resume is _NOTHING:
            raise GraphInterrupt(payload)
        value, self._resume = self._resume, _NOTHING
        return value


# --- given: a fake external payment API -----------------------------------------------------------------------


class IdempotencyConflict(Exception):
    """The same idempotency key was sent with a different payment or amount."""


class SandPayGateway:
    """A fake SandPay refunds API. ``refund`` deduplicates by idempotency key, like a well-behaved payment API.

    ``lose_next_ack = True`` makes the next new refund commit and then raise ``ConnectionError`` - the refund
    happened, but the caller never hears about it.
    """

    def __init__(self, captured: dict[str, int]):
        self.captured = dict(captured)
        self.refunds: list[dict[str, Any]] = []
        self.calls = 0
        self.lose_next_ack = False
        self._by_key: dict[str, dict[str, Any]] = {}

    def refunded_minor(self, payment_id: str) -> int:
        return sum(r["amount_minor"] for r in self.refunds if r["payment_id"] == payment_id)

    def refund(self, payment_id: str, amount_minor: int, idempotency_key: str | None = None) -> dict[str, Any]:
        self.calls += 1
        if idempotency_key is not None and idempotency_key in self._by_key:
            prior = self._by_key[idempotency_key]
            if (prior["payment_id"], prior["amount_minor"]) != (payment_id, amount_minor):
                raise IdempotencyConflict(f"key {idempotency_key!r} was used for a different refund")
            return dict(prior)
        if payment_id not in self.captured:
            raise ValueError(f"unknown payment {payment_id}")
        if amount_minor > self.captured[payment_id] - self.refunded_minor(payment_id):
            raise ValueError("refund exceeds the refundable amount")
        refund = {"refund_id": f"re_{len(self.refunds) + 1:03d}", "payment_id": payment_id, "amount_minor": amount_minor}
        self.refunds.append(refund)
        if idempotency_key is not None:
            self._by_key[idempotency_key] = refund
        if self.lose_next_ack:
            self.lose_next_ack = False
            raise ConnectionError("refund committed, acknowledgement lost")
        return dict(refund)


# --- the runner -------------------------------------------------------------------------------------------------

NodeFn = Callable[[dict[str, Any], Context], dict[str, Any]]


class ApprovalRunner:
    """Runs nodes ``fn(state, ctx) -> update`` with in-memory checkpoints per thread and interrupt/resume.

    A checkpoint is a dict: ``{"checkpoint_id", "parent_id", "next", "values", "interrupt"}``. ``interrupt`` is
    the pending payload when the run is paused at ``next``, otherwise None.
    """

    def __init__(self, nodes: dict[str, NodeFn], routes: dict[str, str | Callable[[dict[str, Any]], str]], entry: str):
        self.nodes = nodes
        self.routes = routes
        self.entry = entry
        self.threads: dict[str, list[dict[str, Any]]] = {}

    def _save(self, thread_id: str, parent: dict[str, Any] | None, next_node: str | None, values: dict[str, Any], interrupt: Any = None) -> dict[str, Any]:
        history = self.threads.setdefault(thread_id, [])
        checkpoint = {
            "checkpoint_id": f"{len(history) + 1:04d}",
            "parent_id": parent["checkpoint_id"] if parent else None,
            "next": next_node,
            "values": copy.deepcopy(values),
            "interrupt": copy.deepcopy(interrupt),
        }
        history.append(checkpoint)
        return checkpoint

    def get_state(self, thread_id: str, checkpoint_id: str | None = None) -> dict[str, Any] | None:
        history = self.threads.get(thread_id, [])
        if checkpoint_id is None:
            return history[-1] if history else None
        return next((c for c in history if c["checkpoint_id"] == checkpoint_id), None)

    def get_state_history(self, thread_id: str) -> list[dict[str, Any]]:
        """Newest first."""
        return list(reversed(self.threads.get(thread_id, [])))

    def _route(self, node: str, values: dict[str, Any]) -> str | None:
        route = self.routes.get(node, END)
        target = route(values) if callable(route) else route
        return None if target == END else target

    def invoke(self, input: dict[str, Any] | Command | None, thread_id: str, checkpoint_id: str | None = None) -> dict[str, Any]:
        """Runs the thread until it finishes or pauses.

        - a dict: new input merged into the latest values; run from the entry node;
        - ``Command(resume=v)``: the latest checkpoint must be paused (else ``NoPendingInterrupt``); re-run its
          node from the start with ``v`` as the answer to its ``interrupt``;
        - None: continue from ``checkpoint_id`` (replay) or the latest checkpoint (retry after an error).

        On ``GraphInterrupt``: save a checkpoint with the same ``next`` and the payload, and return the values
        plus ``"__interrupt__": [payload]``. Any other exception propagates and saves nothing for that node.
        Returns the final values when no node is left.
        """
        raise NotImplementedError


# --- the refund graph -------------------------------------------------------------------------------------------


def refund_key(state: dict[str, Any]) -> str:
    """Idempotency key for the refund. It must be the same every time this case's refund is attempted - on a
    retry, a resume in a new process or a replay - so derive it only from durable state (the support case).
    """
    return f"refund:{uuid.uuid4()}"  # teammate's draft


def build_refund_graph(client: Any, gateway: SandPayGateway) -> ApprovalRunner:
    """draft_refund -> human_review -> issue_refund | close_rejected | human_review (invalid answer) -> END."""

    def draft_refund(state: dict[str, Any], ctx: Context) -> dict[str, Any]:
        reply = client.create(
            system="You are SandPay's support agent. Propose refunds with the propose_refund tool.",
            messages=[{"role": "user", "content": state["message"]}],
            tools=[PROPOSE_REFUND_TOOL],
            max_tokens=200,
            temperature=0,
        )
        if reply.stop_reason != "tool_use":
            return {"status": "no_refund_proposed", "answer": reply.text}
        proposal = reply.tool_calls[0]["input"]
        return {
            "payment_id": proposal["payment_id"],
            "amount_minor": proposal["amount_minor"],
            "reason": proposal["reason"],
            "captured_minor": gateway.captured.get(proposal["payment_id"], 0),
            "status": "awaiting_review",
        }

    def human_review(state: dict[str, Any], ctx: Context) -> dict[str, Any]:
        """Ask the human with ``ctx.interrupt(payload)`` and turn the answer into a state update.

        payload: {"question": "Approve this SandPay refund?", "case_id", "payment_id", "amount_minor",
        "captured_minor", "reason", "error": state.get("review_error")}.
        Answers: {"action": "approve"} -> {"decision": "approve", "review_error": None};
        {"action": "reject", "note": ...} -> {"decision": "reject", "review_error": None, "reject_note": note or ""};
        {"action": "edit", "amount_minor": n} with an int (not bool) 1 <= n <= captured_minor ->
        {"decision": "approve", "amount_minor": n, "edited_by_human": True, "review_error": None};
        an invalid amount -> {"decision": None, "review_error": "amount_minor must be an integer from 1 to <captured>"};
        anything else -> {"decision": None, "review_error": "action must be approve, edit or reject"}.
        No side effects here: this node runs again from its first line when the run resumes.
        """
        raise NotImplementedError

    def issue_refund(state: dict[str, Any], ctx: Context) -> dict[str, Any]:
        refund = gateway.refund(state["payment_id"], state["amount_minor"], idempotency_key=refund_key(state))
        return {"refund": refund, "status": "refunded"}

    def close_rejected(state: dict[str, Any], ctx: Context) -> dict[str, Any]:
        return {"status": "rejected"}

    def after_draft(state: dict[str, Any]) -> str:
        return "human_review" if state.get("status") == "awaiting_review" else END

    def after_review(state: dict[str, Any]) -> str:
        return {"approve": "issue_refund", "reject": "close_rejected"}.get(state.get("decision"), "human_review")

    return ApprovalRunner(
        nodes={
            "draft_refund": draft_refund,
            "human_review": human_review,
            "issue_refund": issue_refund,
            "close_rejected": close_rejected,
        },
        routes={"draft_refund": after_draft, "human_review": after_review, "issue_refund": END, "close_rejected": END},
        entry="draft_refund",
    )
