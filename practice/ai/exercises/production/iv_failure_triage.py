"""Triage a RAG evaluation run: which part of the pipeline failed for each question?

Interview version of "our answer accuracy dropped - where do you look first?". Each record is one golden
question run through SandPay's policy assistant: the chunks that hold the answer (``gold_ids``), the chunks
retrieval put in the prompt, in rank order (``retrieved_ids``), the chunks the answer cites (``cited_ids``)
and the grader's verdict on the answer.

Labels, checked in this order:

1. ``unsupported_citation`` - the answer cites a chunk that was never in the prompt (a grounding defect, even
   when the answer happens to be right).
2. ``pass`` - the answer is right and every citation was in the prompt.
3. ``retrieval_miss`` - no gold chunk was retrieved; the model could not have answered from the context.
4. ``generation_error`` - a gold chunk was in the prompt, but the answer is wrong.
"""

from __future__ import annotations

from dataclasses import dataclass

LABELS = ("pass", "unsupported_citation", "retrieval_miss", "generation_error")

# Fix retrieval before generation: a model cannot use a chunk it never saw.
NEXT_STEP = {
    "unsupported_citation": "Make citations checkable: reject answers that cite chunks outside the prompt.",
    "retrieval_miss": "Fix retrieval first: check chunking, the query, hybrid search and k on the misses.",
    "generation_error": "Fix generation: read the prompts of the failures, then the instructions and context order.",
}
PRIORITY = ("unsupported_citation", "retrieval_miss", "generation_error")


@dataclass(frozen=True)
class EvalRecord:
    query_id: str
    gold_ids: frozenset[str]
    retrieved_ids: tuple[str, ...]
    cited_ids: tuple[str, ...]
    answer_correct: bool


def classify(r: EvalRecord) -> str:
    # TODO: return one of LABELS, checking in the order the module docstring gives.
    # ValueError when gold_ids is empty.
    raise NotImplementedError("classify")


def triage(records: list[EvalRecord]) -> dict[str, int]:
    """Count records per label; every label appears, in LABELS order."""
    # TODO: count classify() of every record; every label appears, in LABELS order.
    raise NotImplementedError("triage")


def next_step(counts: dict[str, int]) -> str:
    """Advice for the largest failure bucket; ties go to the earlier entry in PRIORITY."""
    # TODO: NEXT_STEP for the largest failure bucket in PRIORITY (ties: earlier in PRIORITY wins);
    # "No failures: add harder golden questions before trusting the score." when there are none.
    raise NotImplementedError("next_step")
