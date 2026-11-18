"""SandPay dispute triage as a state graph, built on ``mini_graph`` (solve mini_graph.py first).

Flow (SandPay is fictional; disputes are synthetic):

    START -> classify -> assess_risk -> (route) -> auto_refund -> END
                                               -> escalate    -> END
                                               -> draft_response -> review -> (route) -> finalize -> END
                                                       ^                          |       -> escalate
                                                       +------ problems, retry ---+

- ``classify`` asks the model for one category; anything else becomes ``"other"``.
- ``assess_risk`` is plain code: high risk for fraud or a large amount.
- ``draft_response`` asks the model for the merchant's reply, passing the last review's problems.
- ``review`` checks the draft in code; the graph loops back until it passes or ``max_drafts`` is used up.

The model is injected (``llm.create(messages=..., system=..., max_tokens=..., temperature=...)``), so tests pass
a ``ScriptedLLM``.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from agents.mini_graph import END, START, CompiledGraph, StateGraph

CATEGORIES = ("fraud", "not_received", "duplicate", "other")

CLASSIFY_SYSTEM = (
    "You classify SandPay card disputes. Reply with exactly one word: fraud, not_received, duplicate or other."
)
DRAFT_SYSTEM = (
    "You write a SandPay merchant's reply to a card dispute. Quote the dispute id, state the facts, "
    "promise nothing about the outcome, and stay under the word limit."
)


class TriageState(TypedDict):
    dispute: dict  # id, amount_minor, currency, reason, merchant_id - set once by the caller
    category: str  # overwrite
    risk: str  # overwrite: "high" | "low"
    drafts: int  # overwrite: how many drafts so far
    draft: str  # overwrite: the latest draft only
    problems: list[str]  # overwrite: the latest review's problems only (fed to the next draft)
    review_notes: Annotated[list[str], operator.add]  # append: every problem ever found (audit)
    log: Annotated[list[str], operator.add]  # append: one line per node run
    decision: str  # overwrite: "refund" | "escalate" | "respond"


def initial_state(dispute: dict) -> dict[str, Any]:
    """The input for ``invoke``/``stream``: the dispute, zero drafts and empty append-only lists."""
    return {"dispute": dispute, "drafts": 0, "review_notes": [], "log": []}


def review_draft(draft: str, dispute: dict, max_words: int = 60) -> list[str]:
    """Check a draft in code. Returns the problems, in this order (empty list = pass):

    - ``"missing dispute id <id>"`` when the dispute id does not appear in the draft;
    - ``"too long: <n> words (max <max_words>)"`` when it has more than ``max_words`` words;
    - ``"promises an outcome"`` when it contains "guarantee" in any case.
    """
    problems = []
    if dispute["id"] not in draft:
        problems.append(f"missing dispute id {dispute['id']}")
    words = len(draft.split())
    if words > max_words:
        problems.append(f"too long: {words} words (max {max_words})")
    if "guarantee" in draft.lower():
        problems.append("promises an outcome")
    return problems


def build_triage_graph(
    llm: Any,
    *,
    max_drafts: int = 3,
    high_amount_minor: int = 50_000,
    max_words: int = 60,
) -> CompiledGraph:
    """Build and compile the triage graph. Node names and the ``log`` line each node appends:

    - ``classify``: one model call (system CLASSIFY_SYSTEM, user ``"Dispute <id>: <reason>"``, max_tokens 5,
      temperature 0); category = reply text stripped and lower-cased, or ``"other"`` if not in CATEGORIES.
      Log ``"classify: <category>"``.
    - ``assess_risk``: risk ``"high"`` if category is fraud or amount_minor >= high_amount_minor, else ``"low"``.
      Log ``"assess_risk: <risk>"``.
    - route after assess_risk: high -> ``escalate``; duplicate -> ``auto_refund``; otherwise ``draft_response``.
    - ``draft_response``: one model call (system DRAFT_SYSTEM, temperature 0, max_tokens 200). The user message
      has the dispute id, category, amount and reason; when the last review found problems it ends with
      ``"Fix these problems from the last review:"`` and one ``"- <problem>"`` line each. Sets draft, drafts + 1.
      Log ``"draft_response: attempt <n>"``.
    - ``review``: problems = review_draft(...); sets ``problems``, appends ``"attempt <n>: <problem>"`` to
      review_notes. Log ``"review: ok"`` or ``"review: <k> problem(s)"``.
    - route after review: no problems -> ``finalize``; drafts < max_drafts -> ``draft_response``; else ``escalate``.
    - ``finalize`` / ``auto_refund`` / ``escalate``: decision ``"respond"`` / ``"refund"`` / ``"escalate"``,
      log ``"<node>: <decision>"``; each goes to END.
    """

    def classify(state: dict) -> dict:
        d = state["dispute"]
        reply = llm.create(
            messages=[{"role": "user", "content": f"Dispute {d['id']}: {d['reason']}"}],
            system=CLASSIFY_SYSTEM,
            max_tokens=5,
            temperature=0.0,
        )
        category = reply.text.strip().lower()
        if category not in CATEGORIES:
            category = "other"
        return {"category": category, "log": [f"classify: {category}"]}

    def assess_risk(state: dict) -> dict:
        high = state["category"] == "fraud" or state["dispute"]["amount_minor"] >= high_amount_minor
        risk = "high" if high else "low"
        return {"risk": risk, "log": [f"assess_risk: {risk}"]}

    def route_after_risk(state: dict) -> str:
        if state["risk"] == "high":
            return "escalate"
        if state["category"] == "duplicate":
            return "auto_refund"
        return "draft"

    def draft_response(state: dict) -> dict:
        d = state["dispute"]
        lines = [
            f"Dispute {d['id']} ({state['category']}), amount {d['amount_minor']} minor units {d['currency']}.",
            f"Customer reason: {d['reason']}",
        ]
        if state.get("problems"):
            lines.append("Fix these problems from the last review:")
            lines.extend(f"- {p}" for p in state["problems"])
        reply = llm.create(
            messages=[{"role": "user", "content": "\n".join(lines)}],
            system=DRAFT_SYSTEM,
            max_tokens=200,
            temperature=0.0,
        )
        attempt = state["drafts"] + 1
        return {"draft": reply.text, "drafts": attempt, "log": [f"draft_response: attempt {attempt}"]}

    def review(state: dict) -> dict:
        problems = review_draft(state["draft"], state["dispute"], max_words)
        attempt = state["drafts"]
        summary = "ok" if not problems else f"{len(problems)} problem(s)"
        return {
            "problems": problems,
            "review_notes": [f"attempt {attempt}: {p}" for p in problems],
            "log": [f"review: {summary}"],
        }

    def route_after_review(state: dict) -> str:
        if not state["problems"]:
            return "pass"
        if state["drafts"] < max_drafts:
            return "retry"
        return "give_up"

    def decide(name: str, decision: str):
        def node(state: dict) -> dict:
            return {"decision": decision, "log": [f"{name}: {decision}"]}

        return node

    graph = StateGraph(TriageState)
    graph.add_node("classify", classify)
    graph.add_node("assess_risk", assess_risk)
    graph.add_node("draft_response", draft_response)
    graph.add_node("review", review)
    graph.add_node("finalize", decide("finalize", "respond"))
    graph.add_node("auto_refund", decide("auto_refund", "refund"))
    graph.add_node("escalate", decide("escalate", "escalate"))

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "assess_risk")
    graph.add_conditional_edges(
        "assess_risk",
        route_after_risk,
        {"escalate": "escalate", "auto_refund": "auto_refund", "draft": "draft_response"},
    )
    graph.add_edge("draft_response", "review")
    graph.add_conditional_edges(
        "review",
        route_after_review,
        {"pass": "finalize", "retry": "draft_response", "give_up": "escalate"},
    )
    for name in ("finalize", "auto_refund", "escalate"):
        graph.add_edge(name, END)
    return graph.compile()
