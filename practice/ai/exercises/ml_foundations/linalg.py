"""Vectors and matrices for machine learning - exercise.

Lesson: The maths of machine learning (ml-maths-essentials).
Run: .venv/bin/python -m pytest tests/ml_foundations/test_linalg.py
"""

import numpy as np


def cosine_similarity(a, b):
    """Return the cosine of the angle between two 1-D vectors, a float in [-1, 1].

    cos(theta) = (a . b) / (||a||_2 * ||b||_2)

    Raises ValueError if the vectors are not 1-D, have different lengths, or either has length (norm) 0 -
    the angle to a zero vector is undefined.
    """
    raise NotImplementedError


def predict_scores(X, w, b):
    """Return the linear score X @ w + b for every row of X, as a 1-D array of length n.

    X is an (n, d) matrix (one row per example, one column per feature), w a 1-D vector of length d,
    b a scalar. Raises ValueError, naming both shapes, if X is not 2-D, w is not 1-D, or the number of
    columns of X differs from len(w).
    """
    # A first draft from a colleague. It runs without an error - is it right?
    X = np.asarray(X, dtype=float)
    w = np.asarray(w, dtype=float)
    return np.sum(X * w) + b


def pairwise_sq_distances(A, B):
    """Return the (n, m) matrix of squared Euclidean distances between every row of A and every row of B.

    A is (n, d) and B is (m, d). Use no Python loops: expand
        ||a - b||^2 = ||a||^2 + ||b||^2 - 2 a . b
    with a matrix product for the a . b terms and broadcasting for the sums. Rounding can make an entry
    slightly negative; clip the result at 0. Raises ValueError if the feature counts differ.
    """
    raise NotImplementedError
