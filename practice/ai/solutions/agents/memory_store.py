"""Long-term memory for an agent: store memories per user, retrieve by recency x importance x relevance, forget.

Lesson: agent-memory-and-context. Reference solution.

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
    """Scale to [0, 1]; when every value is the same the feature cannot rank anything, so all become 0."""
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
        if not 1 <= importance <= 10:
            raise ValueError("importance must be between 1 and 10")
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        now = self.clock()
        memory = Memory(self._next_id, user_id, text, kind, float(importance), source, now, now, self.embed_fn(text))
        self._next_id += 1
        self._memories.append(memory)
        return memory

    def retrieve(
        self,
        user_id: str,
        query: str,
        k: int = 3,
        weights: tuple[float, float, float] = (1.0, 1.0, 1.0),
        min_relevance: float | None = None,
    ) -> list[dict[str, Any]]:
        now = self.clock()
        query_vector = self.embed_fn(query)
        candidates = [m for m in self._memories if m.user_id == user_id]
        relevance = np.array([float(query_vector @ m.vector) for m in candidates])
        if min_relevance is not None:
            keep = relevance >= min_relevance
            candidates = [m for m, ok in zip(candidates, keep) if ok]
            relevance = relevance[keep]
        if not candidates:
            return []
        recency = np.array([self.decay ** (now - m.last_accessed) for m in candidates])
        importance = np.array([m.importance for m in candidates])
        parts = (min_max(recency), min_max(importance), min_max(relevance))
        scores = weights[0] * parts[0] + weights[1] * parts[1] + weights[2] * parts[2]
        order = sorted(range(len(candidates)), key=lambda i: (-scores[i], candidates[i].id))[:k]
        results = []
        for i in order:
            results.append(
                {
                    "memory": candidates[i],
                    "score": float(scores[i]),
                    "recency": float(parts[0][i]),
                    "importance": float(parts[1][i]),
                    "relevance": float(parts[2][i]),
                }
            )
            candidates[i].last_accessed = now
        return results

    def forget(self, user_id: str, memory_id: int | None = None) -> int:
        before = len(self._memories)
        self._memories = [
            m for m in self._memories if not (m.user_id == user_id and (memory_id is None or m.id == memory_id))
        ]
        return before - len(self._memories)

    def expire(self, max_idle_hours: float) -> int:
        now = self.clock()
        before = len(self._memories)
        self._memories = [m for m in self._memories if now - m.last_accessed <= max_idle_hours]
        return before - len(self._memories)
