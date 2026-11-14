"""NumPy for machine learning - exercise. Reference solution: solutions/ml_foundations/arrays.py.

Lesson: Python, NumPy and pandas for machine learning (#/lesson/python-numpy-pandas).
Every function is vectorised: no Python loop over rows or elements, and no input array is changed.
"""

import numpy as np


def standardise(X: np.ndarray) -> np.ndarray:
    """Return a float copy of the 2-D array X with every column scaled to mean 0 and standard deviation 1.

    Use the population standard deviation (NumPy's default, ddof=0). A constant column (standard deviation
    0) becomes all zeros instead of NaN. X itself must not change.
    """
    # A first draft: run the tests and read which of them fail, and why.
    return (X - X.mean()) / X.std()


def one_hot(labels: np.ndarray, n_classes: int) -> np.ndarray:
    """Return an (n, n_classes) float array with a 1.0 in column labels[i] of row i and 0.0 elsewhere.

    labels is a 1-D array of integers. Raise ValueError if any label is negative or >= n_classes.
    """
    raise NotImplementedError


def pairwise_sq_distances(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Return the (n, m) array of squared Euclidean distances between every row of A (n, d) and of B (m, d).

    Use broadcasting, not loops. Raise ValueError if the rows have different lengths.
    """
    raise NotImplementedError


def flag_over_limit(amounts: np.ndarray, merchant_idx: np.ndarray, limits: np.ndarray) -> np.ndarray:
    """Return a boolean array: True where amounts[i] is strictly above the limit of its merchant.

    merchant_idx[i] is the position of transaction i's merchant in limits. Use integer-array (fancy)
    indexing to look every limit up at once.
    """
    raise NotImplementedError
