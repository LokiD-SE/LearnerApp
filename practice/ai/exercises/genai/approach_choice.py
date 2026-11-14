"""A transparent decision helper: prompting, RAG or fine-tuning - lesson fine-tuning-vs-rag-vs-prompting.

It turns the arguments of the lesson's sources into a checklist with points, so a team can see WHY a scenario
leans one way. It is a starting hypothesis, not a verdict: the comparison harness (approach_eval.py) decides
with measurements.
"""

from dataclasses import dataclass, field

APPROACHES = ("prompting", "rag", "fine_tuning")  # also the tie-break order: simplest and cheapest first
KNOWLEDGE_CHANGE = ("never", "monthly", "daily")
GAPS = ("none", "knowledge", "format", "style", "skill")


@dataclass(frozen=True)
class Scenario:
    """What we know about the use case before building anything.

    knowledge_change  - how often the facts answers depend on change: "never" | "monthly" | "daily"
    needs_citations   - every answer must point at the source document it came from
    gap               - what the base model still gets wrong with a good prompt:
                        "none" | "knowledge" (missing or private facts) | "format" | "style" | "skill"
    labelled_examples - high-quality input -> ideal output pairs available for training and evaluation
    latency_budget_ms - end-to-end budget per answer
    requests_per_day  - expected traffic
    prompt_tokens     - tokens of instructions and examples a prompt-only solution sends with every request
    """

    knowledge_change: str
    needs_citations: bool
    gap: str
    labelled_examples: int
    latency_budget_ms: int
    requests_per_day: int
    prompt_tokens: int


@dataclass
class Recommendation:
    ranked: list  # viable approaches, best first
    scores: dict  # approach -> points, for every approach (excluded ones too)
    excluded: dict = field(default_factory=dict)  # approach -> reason it is not viable
    reasons: list = field(default_factory=list)  # one line per rule that fired, in rule order


def validate(s):
    """Raise ValueError for an unknown knowledge_change or gap, or a negative number."""
    raise NotImplementedError("validate")


def recommend(s):
    """Score the three approaches for scenario s with these rules, applied in this order:

    1. Baseline: prompting starts at 1, rag and fine_tuning at 0 (always try a good prompt first).
    2. knowledge_change "monthly": rag +2, fine_tuning -1. "daily": rag +3, fine_tuning -2.
    3. needs_citations: rag +2.
    4. gap "none": prompting +2. "knowledge": rag +2. "format": prompting +1, fine_tuning +1.
       "style": fine_tuning +2. "skill": fine_tuning +2.
    5. labelled_examples < 10: fine_tuning is excluded ("fewer than 10 labelled examples").
       10 to 49: fine_tuning -1. 500 or more: fine_tuning +1.
    6. latency_budget_ms < 500: rag -1, fine_tuning +1.
    7. prompt_tokens * requests_per_day >= 50_000_000: fine_tuning +1.

    Each rule that changes a score adds one line to reasons. ranked lists the approaches that are not excluded,
    highest score first; ties keep the order of APPROACHES. Raises ValueError for an invalid scenario.
    """
    raise NotImplementedError("recommend")
