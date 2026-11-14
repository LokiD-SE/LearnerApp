"""Exact (brute-force) vector search with metadata filters, for SandPay's help-centre search.

Vectors are rows of a 2-D float array. Every score is "higher is better": cosine similarity, dot product, or
the *negative* Euclidean (L2) distance, so one top-k function serves all three metrics.
"""

import numpy as np

METRICS = ("cosine", "dot", "l2")


def normalise_rows(x) -> np.ndarray:
    """Return a copy of the (n, d) array ``x`` with every row scaled to Euclidean length 1.

    A row of zeros has no direction: it stays all zeros (no division by zero, no NaN). A 1-D input is treated
    as a single row and a 1-D result is returned.
    """
    x = np.asarray(x, dtype=float)
    one_row = x.ndim == 1
    rows = np.atleast_2d(x)
    norms = np.linalg.norm(rows, axis=1, keepdims=True)
    out = np.divide(rows, norms, out=np.zeros_like(rows), where=norms > 0)
    return out[0] if one_row else out


def similarity(query, matrix, metric="cosine") -> np.ndarray:
    """Score every row of ``matrix`` against the 1-D ``query``; higher means more similar.

    - ``"cosine"``: dot product of the length-normalised vectors (between -1 and 1);
    - ``"dot"``: the raw dot product (rewards long vectors);
    - ``"l2"``: minus the Euclidean distance, so the nearest row gets the highest score.

    Any other metric is a ``ValueError``.
    """
    q = np.asarray(query, dtype=float)
    m = np.atleast_2d(np.asarray(matrix, dtype=float))
    if metric == "cosine":
        return normalise_rows(m) @ normalise_rows(q)
    if metric == "dot":
        return m @ q
    if metric == "l2":
        return -np.linalg.norm(m - q, axis=1)
    raise ValueError(f"metric must be one of {METRICS}, got {metric!r}")


def top_k(scores, k) -> np.ndarray:
    """Positions of the ``k`` highest scores, best first; equal scores keep the lower position first.

    ``k`` larger than the number of scores returns all of them. ``k < 1`` is a ``ValueError``.
    """
    if k < 1:
        raise ValueError(f"k must be at least 1, got {k}")
    s = np.asarray(scores, dtype=float)
    if k < len(s):
        # O(n) partial selection: the k-th best score, then every position at least that good (ties included).
        kth = -np.partition(-s, k - 1)[k - 1]
        candidates = np.flatnonzero(s >= kth)
    else:
        candidates = np.arange(len(s))
    # lexsort sorts by the last key first: highest score, then lowest position.
    order = np.lexsort((candidates, -s[candidates]))
    return candidates[order][:k]


class BruteForceIndex:
    """An exact index: ``search`` scores the query against every stored vector that passes the filter."""

    def __init__(self, dim: int, metric: str = "cosine"):
        if metric not in METRICS:
            raise ValueError(f"metric must be one of {METRICS}, got {metric!r}")
        self.dim = dim
        self.metric = metric
        self.ids: list = []
        self.metadata: list[dict] = []
        self.vectors = np.zeros((0, dim))

    def __len__(self) -> int:
        return len(self.ids)

    def add(self, ids, vectors, metadata=None) -> None:
        """Store vectors under their ids, with an optional metadata dict per vector.

        Raises ``ValueError`` if the number of ids, vectors and metadata rows differ, if a vector does not have
        ``dim`` values, or if an id is already in the index (or repeated in ``ids``). Nothing is stored when it
        raises. For the cosine metric, store the normalised vectors so a search is one matrix product.
        """
        ids = list(ids)
        vectors = np.atleast_2d(np.asarray(vectors, dtype=float))
        metadata = [{} for _ in ids] if metadata is None else [dict(m) for m in metadata]
        if not (len(ids) == len(vectors) == len(metadata)):
            raise ValueError("ids, vectors and metadata must have the same length")
        if vectors.shape[1] != self.dim:
            raise ValueError(f"expected vectors with {self.dim} values, got {vectors.shape[1]}")
        if len(set(ids)) != len(ids) or set(ids) & set(self.ids):
            raise ValueError("ids must be unique")
        if self.metric == "cosine":
            vectors = normalise_rows(vectors)
        self.ids.extend(ids)
        self.metadata.extend(metadata)
        self.vectors = np.vstack([self.vectors, vectors])

    def search(self, query, k: int, where: dict | None = None) -> list[tuple]:
        """The ``k`` best ``(id, score)`` pairs for ``query``, best first.

        ``where`` is a pre-filter: only vectors whose metadata has *every* given key with the given value are
        scored, so a filtered search still returns ``k`` results whenever ``k`` vectors match. Fewer matches
        return fewer results (never an error).
        """
        q = np.asarray(query, dtype=float)
        if q.shape != (self.dim,):
            raise ValueError(f"query must have shape ({self.dim},), got {q.shape}")
        if where:
            positions = np.array(
                [i for i, meta in enumerate(self.metadata) if all(meta.get(f) == v for f, v in where.items())],
                dtype=int,
            )
        else:
            positions = np.arange(len(self.ids))
        if len(positions) == 0:
            return []
        rows = self.vectors[positions] if where else self.vectors  # no copy when there is no filter
        if self.metric == "cosine":
            # The stored rows are already unit length: one matrix-vector product.
            scores = rows @ normalise_rows(q)
        else:
            scores = similarity(q, rows, self.metric)
        best = top_k(scores, k)
        return [(self.ids[positions[i]], float(scores[i])) for i in best]
