"""Vectors and matrices for machine learning - reference solution.

Lesson: The maths of machine learning (ml-maths-essentials).
"""

import numpy as np


def cosine_similarity(a, b):
    """Return the cosine of the angle between two 1-D vectors, a float in [-1, 1].

    cos(theta) = (a . b) / (||a||_2 * ||b||_2)

    Raises ValueError if the vectors are not 1-D, have different lengths, or either has length (norm) 0 -
    the angle to a zero vector is undefined.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.ndim != 1 or b.ndim != 1:
        raise ValueError(f"expected 1-D vectors, got shapes {a.shape} and {b.shape}")
    if a.shape != b.shape:
        raise ValueError(f"vectors have different lengths: {a.shape} and {b.shape}")
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        raise ValueError("cosine similarity is undefined for a zero vector")
    # Clip: rounding can push the ratio a hair past 1 for parallel vectors.
    return float(np.clip(a @ b / (norm_a * norm_b), -1.0, 1.0))


def predict_scores(X, w, b):
    """Return the linear score X @ w + b for every row of X, as a 1-D array of length n.

    X is an (n, d) matrix (one row per example, one column per feature), w a 1-D vector of length d,
    b a scalar. Raises ValueError, naming both shapes, if X is not 2-D, w is not 1-D, or the number of
    columns of X differs from len(w).
    """
    X = np.asarray(X, dtype=float)
    w = np.asarray(w, dtype=float)
    if X.ndim != 2 or w.ndim != 1:
        raise ValueError(f"expected X with 2 dimensions and w with 1, got {X.shape} and {w.shape}")
    if X.shape[1] != w.shape[0]:
        raise ValueError(f"X has {X.shape[1]} columns but w has {w.shape[0]} weights: {X.shape} @ {w.shape}")
    return X @ w + b


def pairwise_sq_distances(A, B):
    """Return the (n, m) matrix of squared Euclidean distances between every row of A and every row of B.

    A is (n, d) and B is (m, d). Use no Python loops: expand
        ||a - b||^2 = ||a||^2 + ||b||^2 - 2 a . b
    with a matrix product for the a . b terms and broadcasting for the sums. Rounding can make an entry
    slightly negative; clip the result at 0. Raises ValueError if the feature counts differ.
    """
    A = np.asarray(A, dtype=float)
    B = np.asarray(B, dtype=float)
    if A.ndim != 2 or B.ndim != 2 or A.shape[1] != B.shape[1]:
        raise ValueError(f"expected (n, d) and (m, d) matrices, got {A.shape} and {B.shape}")
    sq_a = np.sum(A**2, axis=1).reshape(-1, 1)  # (n, 1)
    sq_b = np.sum(B**2, axis=1).reshape(1, -1)  # (1, m)
    d2 = sq_a + sq_b - 2 * A @ B.T  # (n, 1) + (1, m) - (n, m) -> (n, m)
    return np.maximum(d2, 0.0)
