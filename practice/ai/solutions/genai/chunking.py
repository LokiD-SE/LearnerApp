"""Chunking documents for retrieval, and measuring what the chunking does to recall - lesson retrieval-augmented-generation.

A document is Markdown-like text: ``## `` lines start sections. Words are runs of non-whitespace (``text.split()``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    id: str  # "<doc_id>#<n>", n counting from 0 within the document
    doc: str  # the document id
    heading: str  # the section heading ("" for fixed-size chunks and for text before the first heading)
    text: str


def chunk_fixed(doc_id: str, text: str, size: int, overlap: int = 0) -> list[Chunk]:
    """Split ``text`` into windows of ``size`` words; consecutive windows share ``overlap`` words.

    Windows start every ``size - overlap`` words. The last window ends at the last word; a window that would
    only repeat words already in the previous window is not produced. ``heading`` is "" and the chunk text is
    the window's words joined by single spaces. Raise ValueError unless size >= 1 and 0 <= overlap < size.
    An empty text gives an empty list.
    """
    if size < 1 or not 0 <= overlap < size:
        raise ValueError("need size >= 1 and 0 <= overlap < size")
    words = text.split()
    step = size - overlap
    chunks: list[Chunk] = []
    start = 0
    while start < len(words):
        window = words[start : start + size]
        chunks.append(Chunk(f"{doc_id}#{len(chunks)}", doc_id, "", " ".join(window)))
        if start + size >= len(words):
            break
        start += step
    return chunks


def chunk_by_heading(doc_id: str, title: str, text: str, max_words: int | None = None) -> list[Chunk]:
    """One chunk per section, each prefixed with where it came from.

    Sections start at lines beginning with ``## ``; the heading is the rest of that line, stripped. Text
    before the first heading (if it has any words) is a section with heading "". Each chunk's text is
    ``"<title> > <heading>: <body words joined by spaces>"`` (``"<title>: <body>"`` when the heading is "").
    Sections with no body words are skipped. If ``max_words`` is set and a body is longer, split the body
    with chunk_fixed(size=max_words, overlap=0) and give every piece the same prefix and heading.
    Chunk ids are "<doc_id>#0", "#1", ... in order.
    """
    sections: list[tuple[str, list[str]]] = [("", [])]
    for line in text.splitlines():
        match = re.match(r"^## (.*)$", line)
        if match:
            sections.append((match.group(1).strip(), []))
        else:
            sections[-1][1].append(line)

    chunks: list[Chunk] = []
    for heading, lines in sections:
        body = " ".join(" ".join(lines).split())
        if not body:
            continue
        pieces = [body]
        if max_words is not None and len(body.split()) > max_words:
            pieces = [c.text for c in chunk_fixed(doc_id, body, max_words, 0)]
        prefix = f"{title} > {heading}" if heading else title
        for piece in pieces:
            chunks.append(Chunk(f"{doc_id}#{len(chunks)}", doc_id, heading, f"{prefix}: {piece}"))
    return chunks


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


def recall_at_k(results: list[list[Chunk]], facts: list[str], k: int) -> float:
    """Fraction of queries whose top ``k`` retrieved chunks include one that contains the query's fact.

    ``results[i]`` is the ranked chunk list for query i and ``facts[i]`` the text that answers it. Matching
    ignores case and collapses runs of whitespace, so a fact split across two chunks does NOT count. Raise
    ValueError if the lists differ in length or k < 1; an empty list of queries gives 0.0.
    """
    if len(results) != len(facts) or k < 1:
        raise ValueError("results and facts must pair up, and k >= 1")
    if not facts:
        return 0.0
    hits = sum(
        any(_normalise(fact) in _normalise(chunk.text) for chunk in ranked[:k]) for ranked, fact in zip(results, facts)
    )
    return hits / len(facts)
