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
    raise NotImplementedError


def similarity(query, matrix, metric="cosine") -> np.ndarray:
    """Score every row of ``matrix`` against the 1-D ``query``; higher means more similar.

    - ``"cosine"``: dot product of the length-normalised vectors (between -1 and 1);
    - ``"dot"``: the raw dot product (rewards long vectors);
    - ``"l2"``: minus the Euclidean distance, so the nearest row gets the highest score.

    Any other metric is a ``ValueError``.
    """
    raise NotImplementedError


def top_k(scores, k) -> np.ndarray:
    """Positions of the ``k`` highest scores, best first; equal scores keep the lower position first.

    ``k`` larger than the number of scores returns all of them. ``k < 1`` is a ``ValueError``.
    """
    raise NotImplementedError


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
        raise NotImplementedError

    def search(self, query, k: int, where: dict | None = None) -> list[tuple]:
        """The ``k`` best ``(id, score)`` pairs for ``query``, best first.

        ``where`` is a pre-filter: only vectors whose metadata has *every* given key with the given value are
        scored, so a filtered search still returns ``k`` results whenever ``k`` vectors match. Fewer matches
        return fewer results (never an error).
        """
        raise NotImplementedError
