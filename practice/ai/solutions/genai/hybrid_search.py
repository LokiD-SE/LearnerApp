"""Hybrid retrieval: BM25 you write, toy dense vectors, reciprocal rank fusion and a simple reranker -
lesson retrieval-augmented-generation.

Rankings are lists of document indexes, best first. Ties are always broken by the lower index, so every
result is deterministic.
"""

from __future__ import annotations

import math
import re
from collections import Counter

import numpy as np
from toy_embeddings import embed, embed_many

STOPWORDS = frozenset(
    "a an and are as at be by can do does for from how i if in is it my of on or the to what when where which "
    "who why will with you your".split()
)


def tokenize(text: str) -> list[str]:
    """Lower-cased runs of word characters (``\\w+``). Stopwords are kept - BM25's idf discounts them."""
    return re.findall(r"\w+", text.lower())


class BM25:
    """Okapi BM25 over a fixed list of texts.

    idf(t) = ln(1 + (N - n_t + 0.5) / (n_t + 0.5))   (the variant Lucene uses; never negative)
    score(q, d) = sum over query terms t (each occurrence in the query counts) of
                  idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(d) / avg_len))
    where tf is how often t occurs in d, len(d) is d's token count and avg_len the mean over the corpus.
    """

    def __init__(self, texts: list[str], k1: float = 1.2, b: float = 0.75):
        if not texts:
            raise ValueError("BM25 needs at least one text")
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(t)) for t in texts]
        self.lengths = np.array([sum(d.values()) for d in self.docs], dtype=float)
        self.avg_len = float(self.lengths.mean()) or 1.0
        self.df: Counter[str] = Counter()
        for doc in self.docs:
            self.df.update(doc.keys())

    def idf(self, term: str) -> float:
        n_docs, n_t = len(self.docs), self.df.get(term, 0)
        return math.log(1 + (n_docs - n_t + 0.5) / (n_t + 0.5))

    def scores(self, query: str) -> np.ndarray:
        """BM25 score of every text for ``query`` (a float array of length N)."""
        out = np.zeros(len(self.docs))
        norm = self.k1 * (1 - self.b + self.b * self.lengths / self.avg_len)
        for term in tokenize(query):
            if term not in self.df:
                continue
            tf = np.array([doc.get(term, 0) for doc in self.docs], dtype=float)
            out += self.idf(term) * tf * (self.k1 + 1) / (tf + norm)
        return out

    def top_k(self, query: str, k: int) -> list[int]:
        """Indexes of the k best texts with a score above 0, best first (ties: lower index first)."""
        return _top(self.scores(query), k, positive_only=True)


def dense_top_k(query: str, vectors: np.ndarray, k: int) -> list[int]:
    """Indexes of the k rows of ``vectors`` (L2-normalised toy embeddings) most cosine-similar to ``query``."""
    return _top(vectors @ embed(query), k, positive_only=False)


def _top(scores: np.ndarray, k: int, positive_only: bool) -> list[int]:
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    if positive_only:
        order = [i for i in order if scores[i] > 0]
    return order[:k]


def rrf(rankings: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    """Reciprocal rank fusion (Cormack, Clarke and Buettcher, SIGIR 2009).

    Each ranking is a list of document indexes, best first; rank r counts from 1. A document's fused score
    is the sum, over the rankings that contain it, of 1 / (k + r). Return (index, score) pairs sorted by
    score, highest first, ties broken by the lower index. Documents in no ranking are not returned.
    """
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            fused[doc] = fused.get(doc, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda item: (-item[1], item[0]))


def hybrid_top_k(query: str, bm25: BM25, vectors: np.ndarray, k: int, depth: int = 20, rrf_k: int = 60) -> list[int]:
    """Fuse BM25's and the dense search's top ``depth`` lists with rrf and return the best k indexes."""
    lists = [bm25.top_k(query, depth), dense_top_k(query, vectors, depth)]
    return [doc for doc, _ in rrf(lists, rrf_k)[:k]]


def content_terms(text: str) -> list[str]:
    """tokenize() without STOPWORDS, duplicates removed, first occurrence order kept."""
    return list(dict.fromkeys(t for t in tokenize(text) if t not in STOPWORDS))


def rerank_score(query: str, text: str) -> float:
    """A toy reranker that reads the query and the chunk TOGETHER (as a cross-encoder would).

    coverage = share of the query's content terms that appear in the chunk (0 to 1)
    phrase   = share of adjacent content-term pairs of the query that appear next to each other in the chunk's
               content terms (0 when the query has fewer than two content terms)
    score    = 0.8 * coverage + 0.2 * phrase, between 0 and 1. A query with no content terms scores 0.
    """
    q = content_terms(query)
    if not q:
        return 0.0
    chunk_tokens = [t for t in tokenize(text) if t not in STOPWORDS]
    present = set(chunk_tokens)
    coverage = sum(t in present for t in q) / len(q)
    pairs = list(zip(q, q[1:]))
    chunk_pairs = set(zip(chunk_tokens, chunk_tokens[1:]))
    phrase = sum(p in chunk_pairs for p in pairs) / len(pairs) if pairs else 0.0
    return 0.8 * coverage + 0.2 * phrase


def rerank(query: str, texts: list[str], candidates: list[int], top_n: int) -> list[tuple[int, float]]:
    """Re-score the candidate indexes with rerank_score and return the best top_n as (index, score).

    Sort by score, highest first; ties keep the candidates' original order (the first-stage ranking).
    """
    scored = [(i, rerank_score(query, texts[i])) for i in candidates]
    order = sorted(range(len(scored)), key=lambda j: (-scored[j][1], j))
    return [scored[j] for j in order[:top_n]]


__all__ = ["BM25", "STOPWORDS", "content_terms", "dense_top_k", "embed_many", "hybrid_top_k", "rerank", "rerank_score", "rrf", "tokenize"]
