"""Capstone part 1 - the knowledge layer: chunk SandPay's policies, retrieve, and answer only with checked citations.

Exercise: replace each ``raise NotImplementedError`` with code that does what its docstring says, then run the tests (``tests/production/test_<name>.py``). The reference solution is in ``solutions/production/``. Builds on the lessons embeddings-and-vector-search and retrieval-augmented-generation;
vectors come from ``toy_embeddings.embed`` (hashed words, no meaning) so every score is reproducible.

The LLM is passed in: anything with ``create(messages=..., system=..., max_tokens=...)`` returning an object
with ``.text`` (``ScriptedLLM`` in the tests).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from toy_embeddings import embed

REFUSAL = "I can't find that in the SandPay help centre."

SYSTEM_PROMPT = (
    "You are SandPay's merchant support assistant. Answer using ONLY the numbered sources in the user message. "
    "End every sentence with the number of the source that supports it in square brackets, like [2]. "
    f'If the sources do not contain the answer, reply exactly: "{REFUSAL}"'
)


@dataclass(frozen=True)
class Chunk:
    id: str  # "<doc_id>#<heading-slug>", e.g. "refunds#time-limit"
    title: str  # "<document title> - <heading>", e.g. "Refunds - Time limit"
    text: str  # the section body, whitespace collapsed to single spaces


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


@dataclass
class Answer:
    status: str  # "answered" | "refused" | "rejected"
    text: str
    sources: list[str] = field(default_factory=list)  # chunk ids, in prompt order ([1] is sources[0])
    problems: list[str] = field(default_factory=list)


def slugify(heading: str) -> str:
    """Lower case; every run of characters other than a-z and 0-9 becomes one hyphen; no hyphen at either end."""
    raise NotImplementedError("TODO: slugify")


def chunk_policy(doc_id: str, markdown: str) -> list[Chunk]:
    """One chunk per ``## `` section. The ``# `` line is the document title. Sections with no body are skipped;
    text before the first ``## `` is ignored."""
    raise NotImplementedError("TODO: chunk_policy")


class KnowledgeBase:
    """Embeds ``title + " " + text`` of every chunk once; ``search`` ranks by cosine similarity."""

    def __init__(self, chunks: list[Chunk]):
        """Keep the chunks (ValueError "duplicate chunk ids" if two share an id) and embed each one once into
        ``self.matrix``, one row per chunk, so ``search`` is one matrix-vector product."""
        raise NotImplementedError("TODO: KnowledgeBase.__init__")

    def search(self, query: str, k: int = 3, min_score: float = 0.15) -> list[Hit]:
        """The ``k`` best chunks with score >= ``min_score``, best first; ties broken by chunk id. Scores are
        rounded to 3 decimals before sorting and in the returned hits."""
        raise NotImplementedError("TODO: KnowledgeBase.search")


def build_prompt(question: str, hits: list[Hit]) -> str:
    """Numbered sources, a blank line, then the question:

    [1] Refunds - Time limit (refunds#time-limit): A merchant can ...
    [2] ...

    Question: How long ...?"""
    raise NotImplementedError("TODO: build_prompt")


def check_citations(text: str, n_sources: int) -> list[str]:
    """Problems with an answer's citations; an empty list means every sentence is cited correctly.

    A citation may sit before or after the full stop ("... 180 days [1]." or "... 180 days. [1]"): citations
    right after ``.``, ``!`` or ``?`` are first moved in front of it. Then sentences are split after ``.``, ``!``
    or ``?`` followed by whitespace. Each sentence must contain at least one ``[n]``, and every ``n`` must be
    between 1 and ``n_sources``. Problems read ``"sentence 2 has no citation"`` and ``"sentence 1 cites [4], but
    there are only 3 sources"``. The exact refusal is never a problem."""
    raise NotImplementedError("TODO: check_citations")


def answer_question(llm: Any, kb: KnowledgeBase, question: str, k: int = 3, max_tokens: int = 200) -> Answer:
    """Retrieve, ask, check.

    - No hits: return status "refused" with the REFUSAL text WITHOUT calling the model (nothing to ground on).
    - Otherwise call ``llm.create`` once with SYSTEM_PROMPT and one user message holding ``build_prompt``.
    - The reply is exactly REFUSAL: "refused". Citation problems: "rejected" (the text is kept for the logs,
      never shown to the merchant). Otherwise "answered". ``sources`` lists the chunk ids sent, in order."""
    raise NotImplementedError("TODO: answer_question")
