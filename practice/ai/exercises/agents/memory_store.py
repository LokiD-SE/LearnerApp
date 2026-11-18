"""Long-term memory for an agent: store memories per user, retrieve by recency x importance x relevance, forget.

Lesson: agent-memory-and-context. Exercise: implement the methods marked TODO.

The retrieval score follows Park et al., "Generative Agents" (arXiv 2304.03442, section 4.1): recency is an
exponential decay over hours since the memory was last retrieved (decay factor 0.995), importance is a 1-10
rating made when the memory is written, relevance is the cosine similarity between the query's and the
memory's embedding vectors; each is min-max scaled to [0, 1] over the candidates and the three are added with
weights (all 1 in the paper). ``clock()`` returns the current time in hours; tests inject a fake clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
from toy_embeddings import embed

KINDS = ("episodic", "semantic")


@dataclass
class Memory:
    id: int
    user_id: str
    text: str
    kind: str
    importance: float
    source: str
    created_at: float
    last_accessed: float
    vector: np.ndarray = field(repr=False)


def min_max(values: np.ndarray) -> np.ndarray:
    """Scale to [0, 1]; when every value is the same the feature cannot rank anything, so all become 0. Given."""
    low, high = float(values.min()), float(values.max())
    if high == low:
        return np.zeros_like(values, dtype=float)
    return (values - low) / (high - low)


class MemoryStore:
    def __init__(
        self,
        clock: Callable[[], float],
        embed_fn: Callable[[str], np.ndarray] = embed,
        decay: float = 0.995,
    ):
        self.clock = clock
        self.embed_fn = embed_fn
        self.decay = decay
        self._memories: list[Memory] = []
        self._next_id = 1

    def __len__(self) -> int:
        return len(self._memories)

    def add(self, user_id: str, text: str, importance: float, kind: str = "episodic", source: str = "user") -> Memory:
        """Store and return a new ``Memory``.

        - ``importance`` must be within 1..10 and ``kind`` one of ``KINDS``, else ``ValueError``.
        - ids start at 1 and go up by one; ``created_at`` and ``last_accessed`` are ``clock()``;
          ``vector`` is ``embed_fn(text)``.
        """
        raise NotImplementedError  # TODO

    def retrieve(
        self,
        user_id: str,
        query: str,
        k: int = 3,
        weights: tuple[float, float, float] = (1.0, 1.0, 1.0),
        min_relevance: float | None = None,
    ) -> list[dict[str, Any]]:
        """Return the top ``k`` of ``user_id``'s memories for ``query``, best first.

        - Candidates are ONLY this user's memories. Raw relevance = ``embed_fn(query) @ memory.vector``.
        - With ``min_relevance``, drop candidates whose raw relevance is below it BEFORE scaling.
        - No candidates: return ``[]``.
        - Raw recency = ``decay ** (clock() - last_accessed)``; raw importance = ``importance``.
        - Scale each of recency, importance, relevance with ``min_max`` over the candidates; score =
          ``weights[0] * recency + weights[1] * importance + weights[2] * relevance``.
        - Sort by score, highest first; break ties by the lower id.
        - Each result is ``{"memory": Memory, "score": float, "recency": float, "importance": float,
          "relevance": float}`` (the three parts are the SCALED values).
        - Set ``last_accessed = clock()`` on every memory returned (and only those).
        """
        raise NotImplementedError  # TODO

    def forget(self, user_id: str, memory_id: int | None = None) -> int:
        """Delete one of ``user_id``'s memories (``memory_id``), or all of them (``None``); return how many.

        Never delete another user's memory, even when its id is passed.
        """
        raise NotImplementedError  # TODO

    def expire(self, max_idle_hours: float) -> int:
        """Delete every memory not retrieved for more than ``max_idle_hours`` (``clock() - last_accessed``);
        return how many were deleted. Exactly ``max_idle_hours`` idle is kept."""
        raise NotImplementedError  # TODO
