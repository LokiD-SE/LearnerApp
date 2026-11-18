"""Capstone part 1 - the knowledge layer: chunk SandPay's policies, retrieve, and answer only with checked citations.

Reference solution. Builds on the lessons embeddings-and-vector-search and retrieval-augmented-generation;
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
    return re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")


def chunk_policy(doc_id: str, markdown: str) -> list[Chunk]:
    """One chunk per ``## `` section. The ``# `` line is the document title. Sections with no body are skipped;
    text before the first ``## `` is ignored."""
    title = doc_id
    chunks: list[Chunk] = []
    heading: str | None = None
    body: list[str] = []

    def flush() -> None:
        text = " ".join(" ".join(body).split())
        if heading is not None and text:
            chunks.append(Chunk(f"{doc_id}#{slugify(heading)}", f"{title} - {heading}", text))

    for line in markdown.splitlines():
        if line.startswith("## "):
            flush()
            heading, body = line[3:].strip(), []
        elif line.startswith("# "):
            title = line[2:].strip()
        elif heading is not None:
            body.append(line)
    flush()
    return chunks


class KnowledgeBase:
    """Embeds ``title + " " + text`` of every chunk once; ``search`` ranks by cosine similarity."""

    def __init__(self, chunks: list[Chunk]):
        """Keep the chunks (ValueError "duplicate chunk ids" if two share an id) and embed each one once into
        ``self.matrix``, one row per chunk, so ``search`` is one matrix-vector product."""
        ids = [c.id for c in chunks]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate chunk ids")
        self.chunks = list(chunks)
        self.matrix = np.stack([embed(f"{c.title} {c.text}") for c in chunks]) if chunks else np.zeros((0, 1))

    def search(self, query: str, k: int = 3, min_score: float = 0.15) -> list[Hit]:
        """The ``k`` best chunks with score >= ``min_score``, best first; ties broken by chunk id. Scores are
        rounded to 3 decimals before sorting and in the returned hits."""
        if not self.chunks or k < 1:
            return []
        scores = self.matrix @ embed(query)
        hits = [Hit(c, round(float(s), 3)) for c, s in zip(self.chunks, scores) if round(float(s), 3) >= min_score]
        hits.sort(key=lambda h: (-h.score, h.chunk.id))
        return hits[:k]


def build_prompt(question: str, hits: list[Hit]) -> str:
    """Numbered sources, a blank line, then the question:

    [1] Refunds - Time limit (refunds#time-limit): A merchant can ...
    [2] ...

    Question: How long ...?"""
    lines = [f"[{i}] {h.chunk.title} ({h.chunk.id}): {h.chunk.text}" for i, h in enumerate(hits, 1)]
    return "\n".join(lines) + f"\n\nQuestion: {question}"


def check_citations(text: str, n_sources: int) -> list[str]:
    """Problems with an answer's citations; an empty list means every sentence is cited correctly.

    A citation may sit before or after the full stop ("... 180 days [1]." or "... 180 days. [1]"): citations
    right after ``.``, ``!`` or ``?`` are first moved in front of it. Then sentences are split after ``.``, ``!``
    or ``?`` followed by whitespace. Each sentence must contain at least one ``[n]``, and every ``n`` must be
    between 1 and ``n_sources``. Problems read ``"sentence 2 has no citation"`` and ``"sentence 1 cites [4], but
    there are only 3 sources"``. The exact refusal is never a problem."""
    if text.strip() == REFUSAL:
        return []
    problems: list[str] = []
    normalised = re.sub(r"([.!?])((?:\s*\[\d+\])+)", r"\2\1", text.strip())
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", normalised) if s.strip()]
    for number, sentence in enumerate(sentences, 1):
        cited = [int(n) for n in re.findall(r"\[(\d+)\]", sentence)]
        if not cited:
            problems.append(f"sentence {number} has no citation")
        for n in cited:
            if not 1 <= n <= n_sources:
                problems.append(f"sentence {number} cites [{n}], but there are only {n_sources} sources")
    return problems


def answer_question(llm: Any, kb: KnowledgeBase, question: str, k: int = 3, max_tokens: int = 200) -> Answer:
    """Retrieve, ask, check.

    - No hits: return status "refused" with the REFUSAL text WITHOUT calling the model (nothing to ground on).
    - Otherwise call ``llm.create`` once with SYSTEM_PROMPT and one user message holding ``build_prompt``.
    - The reply is exactly REFUSAL: "refused". Citation problems: "rejected" (the text is kept for the logs,
      never shown to the merchant). Otherwise "answered". ``sources`` lists the chunk ids sent, in order."""
    hits = kb.search(question, k=k)
    if not hits:
        return Answer("refused", REFUSAL)
    sources = [h.chunk.id for h in hits]
    reply = llm.create(
        messages=[{"role": "user", "content": build_prompt(question, hits)}],
        system=SYSTEM_PROMPT,
        max_tokens=max_tokens,
    )
    text = reply.text.strip()
    if text == REFUSAL:
        return Answer("refused", text, sources)
    problems = check_citations(text, len(hits))
    return Answer("rejected" if problems else "answered", text, sources, problems)
