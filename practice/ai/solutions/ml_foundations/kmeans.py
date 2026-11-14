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
    X = np.asarray(X, dtype=float)
    n = len(X)
    if not 1 <= k <= n:
        raise ValueError(f"k must be between 1 and {n}, got {k}")
    centres = [X[rng.integers(n)]]
    d2 = np.sum((X - centres[0]) ** 2, axis=1)
    for _ in range(1, k):
        total = d2.sum()
        # Every point coincides with a centre already: any row will do.
        p = d2 / total if total > 0 else np.full(n, 1 / n)
        centres.append(X[rng.choice(n, p=p)])
        d2 = np.minimum(d2, np.sum((X - centres[-1]) ** 2, axis=1))
    return np.array(centres)


def assign(X, centroids) -> np.ndarray:
    """Index of the nearest centroid (squared Euclidean distance) for every row; ties go to the lower index."""
    X = np.asarray(X, dtype=float)
    d2 = np.sum((X[:, None, :] - np.asarray(centroids)[None, :, :]) ** 2, axis=2)
    return np.argmin(d2, axis=1)


def update(X, labels, old_centroids) -> np.ndarray:
    """Move each centroid to the mean of the rows assigned to it.

    A cluster that has no rows keeps its old centroid (no division by zero, no NaN).
    """
    X = np.asarray(X, dtype=float)
    new = np.array(old_centroids, dtype=float, copy=True)
    for j in range(len(new)):
        members = X[labels == j]
        if len(members):
            new[j] = members.mean(axis=0)
    return new


def inertia(X, centroids, labels) -> float:
    """Sum of squared distances from every row to its assigned centroid (scikit-learn's ``inertia_``)."""
    X = np.asarray(X, dtype=float)
    return float(np.sum((X - np.asarray(centroids)[labels]) ** 2))


def lloyd(X, k, rng, max_iter=300, tol=1e-6):
    """Run k-means: k-means++ seeding, then assign and update until no centroid moves more than ``tol``
    (Euclidean distance) or ``max_iter`` iterations have run.

    Return ``(centroids, labels, history)`` where ``labels`` is assigned to the final centroids and
    ``history`` lists the inertia after every assignment step (it never increases).
    """
    X = np.asarray(X, dtype=float)
    centroids = kmeans_plus_plus(X, k, rng)
    history = []
    for _ in range(max_iter):
        labels = assign(X, centroids)
        history.append(inertia(X, centroids, labels))
        new = update(X, labels, centroids)
        moved = np.max(np.linalg.norm(new - centroids, axis=1))
        centroids = new
        if moved <= tol:
            break
    labels = assign(X, centroids)
    return centroids, labels, history


def best_of(X, k, n_init, seed):
    """Run ``lloyd`` ``n_init`` times from ``numpy.random.default_rng(seed)`` (one generator shared by all
    runs) and return the ``(centroids, labels, inertia)`` of the run with the lowest final inertia."""
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(n_init):
        centroids, labels, _ = lloyd(X, k, rng)
        score = inertia(X, centroids, labels)
        if best is None or score < best[2]:
            best = (centroids, labels, score)
    return best
