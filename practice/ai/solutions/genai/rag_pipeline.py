"""Grounded answers with numbered sources and checked citations - lesson retrieval-augmented-generation.

The client is passed in (a ScriptedLLM in the tests, a real SDK wrapper in production): anything with
``create(messages=..., system=..., max_tokens=..., temperature=...)`` returning an object with ``.text``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

REFUSAL = "I can't find that in the SandPay help centre."

SYSTEM_PROMPT = (
    "You answer questions about SandPay using ONLY the numbered sources in the user message. "
    "Put the number of the source that supports each sentence in square brackets after it, like [2]. "
    f'If the sources do not contain the answer, reply exactly: "{REFUSAL}"'
)


@dataclass(frozen=True)
class Source:
    title: str
    text: str


@dataclass
class Answer:
    status: str  # "answered" | "refused" | "rejected"
    text: str  # what the user sees
    sources: list[Source] = field(default_factory=list)
    cited: list[int] = field(default_factory=list)  # source numbers the answer cites, sorted, no repeats
    problems: list[str] = field(default_factory=list)


def build_prompt(question: str, sources: list[Source]) -> str:
    """The user message: the numbered sources, then the question - in this exact layout::

        <sources>
        [1] <title of source 1>
        <text of source 1>

        [2] <title of source 2>
        <text of source 2>
        </sources>

        Question: <question>

    Sources are numbered from 1 in the order given (most relevant first). With no sources the block is
    "<sources>\\n</sources>".
    """
    blocks = [f"[{n}] {s.title}\n{s.text}" for n, s in enumerate(sources, start=1)]
    return "<sources>\n" + "\n\n".join(blocks) + ("\n" if blocks else "") + f"</sources>\n\nQuestion: {question}"


def extract_citations(answer: str) -> list[int]:
    """Every source number cited as ``[n]`` (also ``[n, m]``), in order of appearance, repeats kept."""
    found: list[int] = []
    for group in re.findall(r"\[(\d+(?:\s*,\s*\d+)*)\]", answer):
        found.extend(int(n) for n in group.split(","))
    return found


def check_citations(answer: str, n_sources: int) -> list[str]:
    """Problems with a model's answer; an empty list means it may be shown.

    - The exact REFUSAL (after stripping whitespace) is always fine.
    - "no citations" if the answer cites nothing.
    - "cites [n]: no such source (N given)" for each distinct n outside 1..N (in order of appearance).
    - "uncited sentence: <sentence>" for each sentence without a citation. Sentences are the pieces of the
      stripped answer split after ".", "!" or "?" followed by whitespace; empty pieces are ignored. A
      citation that directly follows the end mark (``... days. [2]``) belongs to the sentence before it.
    """
    text = answer.strip()
    if text == REFUSAL:
        return []
    cited = extract_citations(text)
    if not cited:
        return ["no citations"]
    problems = []
    for n in dict.fromkeys(cited):
        if not 1 <= n <= n_sources:
            problems.append(f"cites [{n}]: no such source ({n_sources} given)")
    # Move a citation that follows the full stop to before it, then split into sentences.
    moved = re.sub(r"([.!?])((?:\s*\[\d+(?:\s*,\s*\d+)*\])+)", r"\2\1", text)
    for sentence in re.split(r"(?<=[.!?])\s+", moved):
        if sentence.strip() and not extract_citations(sentence):
            problems.append(f"uncited sentence: {sentence.strip()}")
    return problems


Retriever = Callable[[str], list[tuple[Source, float]]]


def answer_question(question: str, retrieve: Retriever, client, min_score: float = 0.5, max_sources: int = 3) -> Answer:
    """Retrieve, gate, prompt, check.

    1. ``retrieve(question)`` returns (source, relevance score) pairs, best first. Keep the first
       ``max_sources`` whose score is at least ``min_score``.
    2. If none are left, return status "refused" with REFUSAL - and do NOT call the model.
    3. Otherwise call ``client.create`` once with system=SYSTEM_PROMPT, one user message
       build_prompt(question, kept), max_tokens=300 and temperature=0.
    4. If the reply is the REFUSAL, status "refused". If check_citations finds problems, status "rejected",
       text REFUSAL (never show an unsupported answer) and the problems listed. Otherwise "answered" with
       the reply text. ``sources`` is the kept list and ``cited`` the sorted distinct numbers cited.
    """
    kept = [source for source, score in retrieve(question) if score >= min_score][:max_sources]
    if not kept:
        return Answer("refused", REFUSAL)
    reply = client.create(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_prompt(question, kept)}],
        max_tokens=300,
        temperature=0,
    ).text.strip()
    cited = sorted(set(extract_citations(reply)))
    if reply == REFUSAL:
        return Answer("refused", REFUSAL, kept, cited)
    problems = check_citations(reply, len(kept))
    if problems:
        return Answer("rejected", REFUSAL, kept, cited, problems)
    return Answer("answered", reply, kept, cited)
