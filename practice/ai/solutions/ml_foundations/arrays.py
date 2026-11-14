"""NumPy for machine learning - reference solution.

Lesson: Python, NumPy and pandas for machine learning (#/lesson/python-numpy-pandas).
Every function is vectorised: no Python loop over rows or elements, and no input array is changed.
"""

import numpy as np


def standardise(X: np.ndarray) -> np.ndarray:
    """Return a float copy of the 2-D array X with every column scaled to mean 0 and standard deviation 1.

    Use the population standard deviation (NumPy's default, ddof=0). A constant column (standard deviation
    0) becomes all zeros instead of NaN. X itself must not change.
    """
    X = np.asarray(X, dtype=np.float64)
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    # Divide by 1 where a column is constant: (x - mean) is already 0 there.
    safe = np.where(std == 0, 1.0, std)
    return (X - mean) / safe


def one_hot(labels: np.ndarray, n_classes: int) -> np.ndarray:
    """Return an (n, n_classes) float array with a 1.0 in column labels[i] of row i and 0.0 elsewhere.

    labels is a 1-D array of integers. Raise ValueError if any label is negative or >= n_classes.
    """
    labels = np.asarray(labels)
    if labels.size and (labels.min() < 0 or labels.max() >= n_classes):
        raise ValueError(f"labels must be in [0, {n_classes})")
    out = np.zeros((labels.shape[0], n_classes))
    out[np.arange(labels.shape[0]), labels] = 1.0
    return out


def pairwise_sq_distances(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Return the (n, m) array of squared Euclidean distances between every row of A (n, d) and of B (m, d).

    Use broadcasting, not loops. Raise ValueError if the rows have different lengths.
    """
    A = np.asarray(A, dtype=np.float64)
    B = np.asarray(B, dtype=np.float64)
    if A.shape[1] != B.shape[1]:
        raise ValueError(f"rows have {A.shape[1]} and {B.shape[1]} features")
    # (n, 1, d) - (1, m, d) broadcasts to (n, m, d); sum over the feature axis.
    diff = A[:, np.newaxis, :] - B[np.newaxis, :, :]
    return (diff**2).sum(axis=2)


def flag_over_limit(amounts: np.ndarray, merchant_idx: np.ndarray, limits: np.ndarray) -> np.ndarray:
    """Return a boolean array: True where amounts[i] is strictly above the limit of its merchant.

    merchant_idx[i] is the position of transaction i's merchant in limits. Use integer-array (fancy)
    indexing to look every limit up at once.
    """
    return np.asarray(amounts) > np.asarray(limits)[np.asarray(merchant_idx)]
