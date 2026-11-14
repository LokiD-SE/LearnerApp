"""Principal component analysis with NumPy's SVD, for SandPay's 24-hour merchant volume profiles.

``X`` is an (n, d) array with one row per merchant. Fit on training rows; transform any rows. The tests
compare your results with scikit-learn's ``PCA`` (principal directions are only defined up to sign, so the
sign convention below makes them comparable).
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class PCAModel:
    mean: np.ndarray  # (d,) the training mean that was subtracted
    components: np.ndarray  # (k, d) unit-length principal directions, largest variance first
    explained_variance: np.ndarray  # (k,) variance of the training data along each direction (ddof=1)
    explained_variance_ratio: np.ndarray  # (k,) that variance divided by the total variance


def fit_pca(X, n_components) -> PCAModel:
    """Fit PCA: centre X on its column means, take the SVD, keep the first ``n_components`` directions.

    Sign convention: flip each direction so that its entry with the largest absolute value is positive.
    Explained variance is S**2 / (n - 1); the ratio divides by the total variance of all directions.
    """
    X = np.asarray(X, dtype=float)
    n, d = X.shape
    if not 1 <= n_components <= min(n, d):
        raise ValueError(f"n_components must be between 1 and {min(n, d)}, got {n_components}")
    mean = X.mean(axis=0)
    _, S, Vt = np.linalg.svd(X - mean, full_matrices=False)
    signs = np.sign(Vt[np.arange(len(Vt)), np.argmax(np.abs(Vt), axis=1)])
    Vt = Vt * signs[:, None]
    variance = S**2 / (n - 1)
    return PCAModel(
        mean=mean,
        components=Vt[:n_components],
        explained_variance=variance[:n_components],
        explained_variance_ratio=(variance / variance.sum())[:n_components],
    )


def transform(model: PCAModel, X, whiten=False) -> np.ndarray:
    """Project rows onto the components: (X - mean) @ components.T. With ``whiten=True`` divide each score
    by the square root of its explained variance, so every component has variance 1 on the training data."""
    Z = (np.asarray(X, dtype=float) - model.mean) @ model.components.T
    if whiten:
        Z = Z / np.sqrt(model.explained_variance)
    return Z


def inverse_transform(model: PCAModel, Z) -> np.ndarray:
    """Map (unwhitened) scores back to the original space: Z @ components + mean."""
    return np.asarray(Z, dtype=float) @ model.components + model.mean


def reconstruction_error(model: PCAModel, X) -> np.ndarray:
    """Squared distance between each row and its reconstruction from the kept components - large for rows
    the components do not describe."""
    X = np.asarray(X, dtype=float)
    return np.sum((X - inverse_transform(model, transform(model, X))) ** 2, axis=1)


def components_for_variance(X, target) -> int:
    """The smallest number of components whose cumulative explained variance ratio reaches ``target``
    (0 < target <= 1), as ``PCA(n_components=target)`` chooses it."""
    if not 0 < target <= 1:
        raise ValueError(f"target must be in (0, 1], got {target}")
    X = np.asarray(X, dtype=float)
    ratio = fit_pca(X, min(X.shape)).explained_variance_ratio
    # A tiny tolerance stops rounding error from asking for one more component when target is 1.0.
    return int(np.searchsorted(np.cumsum(ratio), target - 1e-12) + 1)
