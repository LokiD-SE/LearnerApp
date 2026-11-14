"""k-means from scratch: k-means++ seeding and Lloyd's algorithm, for SandPay merchant segments.

``X`` is an (n, d) float array of already-scaled features. ``rng`` is a ``numpy.random.Generator``; use only
it for randomness, so a fixed seed gives the same clusters every run. The tests compare your results with
scikit-learn's ``KMeans``.
"""

import numpy as np


def kmeans_plus_plus(X, k, rng) -> np.ndarray:
    """Choose k initial centroids with k-means++ (Arthur and Vassilvitskii, 2007).

    The first centre is a row of X chosen uniformly at random (``rng.integers``). Each next centre is a row
    chosen with probability proportional to D(x)^2, the squared distance from x to its nearest centre
    chosen so far (``rng.choice(n, p=...)``). Return a (k, d) array of copies of the chosen rows.
    """
    raise NotImplementedError


def assign(X, centroids) -> np.ndarray:
    """Index of the nearest centroid (squared Euclidean distance) for every row; ties go to the lower index."""
    raise NotImplementedError


def update(X, labels, old_centroids) -> np.ndarray:
    """Move each centroid to the mean of the rows assigned to it.

    A cluster that has no rows keeps its old centroid (no division by zero, no NaN).
    """
    # First draft - it passes the happy path. Check what happens when a cluster gets no rows.
    X = np.asarray(X, dtype=float)
    new = np.empty_like(np.asarray(old_centroids, dtype=float))
    for j in range(len(new)):
        new[j] = X[labels == j].mean(axis=0)
    return new


def inertia(X, centroids, labels) -> float:
    """Sum of squared distances from every row to its assigned centroid (scikit-learn's ``inertia_``)."""
    raise NotImplementedError


def lloyd(X, k, rng, max_iter=300, tol=1e-6):
    """Run k-means: k-means++ seeding, then assign and update until no centroid moves more than ``tol``
    (Euclidean distance) or ``max_iter`` iterations have run.

    Return ``(centroids, labels, history)`` where ``labels`` is assigned to the final centroids and
    ``history`` lists the inertia after every assignment step (it never increases).
    """
    raise NotImplementedError


def best_of(X, k, n_init, seed):
    """Run ``lloyd`` ``n_init`` times from ``numpy.random.default_rng(seed)`` (one generator shared by all
    runs) and return the ``(centroids, labels, inertia)`` of the run with the lowest final inertia."""
    raise NotImplementedError
