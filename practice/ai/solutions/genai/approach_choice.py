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
    if s.knowledge_change not in KNOWLEDGE_CHANGE:
        raise ValueError(f"knowledge_change must be one of {KNOWLEDGE_CHANGE}, got {s.knowledge_change!r}")
    if s.gap not in GAPS:
        raise ValueError(f"gap must be one of {GAPS}, got {s.gap!r}")
    for name in ("labelled_examples", "latency_budget_ms", "requests_per_day", "prompt_tokens"):
        if getattr(s, name) < 0:
            raise ValueError(f"{name} must not be negative")


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
    validate(s)
    scores = {"prompting": 1, "rag": 0, "fine_tuning": 0}
    excluded, reasons = {}, []

    def add(points, why):
        for name, delta in points.items():
            scores[name] += delta
        reasons.append(why)

    if s.knowledge_change == "monthly":
        add({"rag": 2, "fine_tuning": -1}, "facts change monthly: update an index, not the weights")
    elif s.knowledge_change == "daily":
        add({"rag": 3, "fine_tuning": -2}, "facts change daily: retraining cannot keep up")
    if s.needs_citations:
        add({"rag": 2}, "citations needed: retrieved chunks give provenance")
    gap_rules = {
        "none": ({"prompting": 2}, "no gap left with a good prompt: keep prompting"),
        "knowledge": ({"rag": 2}, "missing or private facts: put them in the context"),
        "format": ({"prompting": 1, "fine_tuning": 1}, "format gap: few-shot examples first, fine-tune if not consistent"),
        "style": ({"fine_tuning": 2}, "style gap: demonstrations teach behaviour"),
        "skill": ({"fine_tuning": 2}, "skill gap: demonstrations teach behaviour"),
    }
    add(*gap_rules[s.gap])
    if s.labelled_examples < 10:
        excluded["fine_tuning"] = "fewer than 10 labelled examples"
    elif s.labelled_examples < 50:
        add({"fine_tuning": -1}, "under 50 labelled examples: too few to train and evaluate well")
    elif s.labelled_examples >= 500:
        add({"fine_tuning": 1}, "500+ labelled examples: enough to train and hold out a test set")
    if s.latency_budget_ms < 500:
        add({"rag": -1, "fine_tuning": 1}, "tight latency: retrieval adds a step, a tuned model needs a shorter prompt")
    if s.prompt_tokens * s.requests_per_day >= 50_000_000:
        add({"fine_tuning": 1}, "heavy prompt volume: shorter prompts save tokens at scale")

    ranked = sorted((a for a in APPROACHES if a not in excluded), key=lambda a: (-scores[a], APPROACHES.index(a)))
    return Recommendation(ranked, scores, excluded, reasons)
