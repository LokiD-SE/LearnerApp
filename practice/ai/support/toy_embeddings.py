"""Deterministic toy text embeddings for vector-search and RAG exercises (no model download).

``embed(text)`` hashes lower-cased word unigrams and bigrams into a fixed-size vector and L2-normalises it, so
texts that share words get a high cosine similarity. It knows nothing about meaning (synonyms score 0) - the
lessons use that gap to show why real embedding models exist.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np

DIM = 256


def _bucket(feature: str) -> tuple[int, float]:
    digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
    value = int.from_bytes(digest, "little")
    return value % DIM, 1.0 if (value >> 32) & 1 else -1.0


def embed(text: str, dim: int = DIM) -> np.ndarray:
    words = re.findall(r"\w+", text.lower())
    features = words + [f"{a} {b}" for a, b in zip(words, words[1:])]
    vector = np.zeros(dim)
    for feature in features:
        index, sign = _bucket(feature)
        vector[index % dim] += sign
    norm = np.linalg.norm(vector)
    return vector / norm if norm else vector


def embed_many(texts: list[str], dim: int = DIM) -> np.ndarray:
    return np.stack([embed(t, dim) for t in texts]) if texts else np.zeros((0, dim))
