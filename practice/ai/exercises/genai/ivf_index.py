"""An approximate vector index: an inverted file (IVF) built with k-means, as in Johnson, Douze and Jegou,
"Billion-scale similarity search with GPUs" (arXiv:1702.08734), without the compression step.

Training clusters the (normalised) vectors into ``n_lists`` cells with k-means. Each stored vector goes into the
inverted list of its nearest centroid. A search compares the query with the centroids, scans only the ``nprobe``
nearest lists, and returns the best ``k`` of the vectors found there, scored by cosine similarity. More probes
mean higher recall and more work; ``nprobe == n_lists`` scans everything and equals exact search.
"""

import numpy as np



def normalise_rows(x) -> np.ndarray:
    """Rows scaled to length 1; zero rows stay zero (provided - the same helper as in vector_index.py)."""
    x = np.asarray(x, dtype=float)
    rows = np.atleast_2d(x)
    norms = np.linalg.norm(rows, axis=1, keepdims=True)
    out = np.divide(rows, norms, out=np.zeros_like(rows), where=norms > 0)
    return out[0] if x.ndim == 1 else out


def top_k(scores, k) -> np.ndarray:
    """Positions of the k highest scores, best first, ties to the lower position (provided)."""
    s = np.asarray(scores, dtype=float)
    if k < len(s):
        candidates = np.flatnonzero(s >= -np.partition(-s, k - 1)[k - 1])
    else:
        candidates = np.arange(len(s))
    return candidates[np.lexsort((candidates, -s[candidates]))][:k]


def kmeans(x, n_clusters: int, n_iter: int = 20, seed: int = 0) -> np.ndarray:
    """Lloyd's k-means (provided). Starts from ``n_clusters`` distinct rows chosen with ``seed``.

    Returns the (n_clusters, d) centroids. A cluster that loses all its rows keeps its old centroid.
    Distances use ||x - c||^2 = ||x||^2 - 2 x.c + ||c||^2, so no (n, k, d) array is built.
    """
    x = np.asarray(x, dtype=float)
    if not 1 <= n_clusters <= len(x):
        raise ValueError(f"n_clusters must be between 1 and {len(x)}, got {n_clusters}")
    rng = np.random.default_rng(seed)
    centroids = x[rng.choice(len(x), size=n_clusters, replace=False)].copy()
    for _ in range(n_iter):
        labels = nearest_centroids(x, centroids, 1)[:, 0]
        for j in range(n_clusters):
            members = x[labels == j]
            if len(members):
                centroids[j] = members.mean(axis=0)
    return centroids


def nearest_centroids(x, centroids, n: int) -> np.ndarray:
    """For every row of ``x``, the positions of its ``n`` nearest centroids (squared L2), nearest first.

    Equal distances keep the lower centroid position first. Returns an (len(x), n) int array.
    """
    raise NotImplementedError


class IVFIndex:
    """Inverted-file index over cosine similarity."""

    def __init__(self, n_lists: int, seed: int = 0, n_iter: int = 20):
        self.n_lists = n_lists
        self.seed = seed
        self.n_iter = n_iter
        self.centroids = None
        self.ids: list = []
        self.vectors = None  # (n, d), normalised
        self.lists: list[np.ndarray] = []  # positions into ids/vectors, one array per centroid
        self.last_scanned = 0  # how many stored vectors the last search scored

    def train(self, vectors) -> None:
        """Learn the ``n_lists`` centroids from (normalised) training vectors with ``kmeans``."""
        self.centroids = kmeans(normalise_rows(vectors), self.n_lists, self.n_iter, self.seed)
        self.vectors = np.zeros((0, self.centroids.shape[1]))
        self.lists = [np.zeros(0, dtype=int) for _ in range(self.n_lists)]

    def add(self, ids, vectors) -> None:
        """Normalise the vectors, store them, and append each position to its nearest centroid's list.

        ``RuntimeError`` if the index is not trained; ``ValueError`` if ids and vectors differ in length.
        """
        raise NotImplementedError

    def search(self, query, k: int, nprobe: int = 1) -> list[tuple]:
        """The best ``k`` ``(id, score)`` pairs among the vectors in the ``nprobe`` nearest lists, best first.

        ``nprobe`` above ``n_lists`` is capped at ``n_lists``; below 1 it is a ``ValueError``. Candidates are
        scored in order of position, so equal scores keep the earlier-added vector first, exactly like
        ``BruteForceIndex``. Sets ``last_scanned`` to the number of candidates scored.
        """
        raise NotImplementedError
