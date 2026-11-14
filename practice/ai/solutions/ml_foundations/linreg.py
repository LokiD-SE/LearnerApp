"""Linear regression from first principles - the hypothesis, the cost, its gradient and the normal equation.

Conventions (as in the CS229 notes): ``X`` is the design matrix, one row per example, shape ``(n, d)``; ``y`` has
shape ``(n,)``; ``theta`` has shape ``(d,)``. Add the intercept column yourself with :func:`add_intercept`, so
``theta[0]`` is the intercept.
"""

import numpy as np


def add_intercept(X: np.ndarray) -> np.ndarray:
    """Return ``X`` with a first column of ones (the x0 = 1 feature), as a new float array.

    A 1-D ``X`` is one feature: shape ``(n,)`` becomes ``(n, 2)``. ``X`` itself is not changed.
    """
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    return np.column_stack([np.ones(X.shape[0]), X])


def predict(X: np.ndarray, theta: np.ndarray) -> np.ndarray:
    """The hypothesis h(x) = theta . x for every row of ``X`` - a vector of shape ``(n,)``."""
    return np.asarray(X, dtype=float) @ np.asarray(theta, dtype=float)


def mse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean squared error: the mean of (prediction - target)**2, as a Python float.

    This is what ``sklearn.metrics.mean_squared_error`` reports. Raise ``ValueError`` if the shapes differ -
    broadcasting a ``(n, 1)`` column against an ``(n,)`` vector would silently give an ``(n, n)`` matrix.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if y_true.shape != y_pred.shape:
        raise ValueError(f"shapes differ: {y_true.shape} and {y_pred.shape}")
    return float(np.mean((y_pred - y_true) ** 2))


def cost(X: np.ndarray, y: np.ndarray, theta: np.ndarray) -> float:
    """The cost J(theta) = (1 / 2n) * sum((X @ theta - y)**2) - half the mean squared error.

    The 1/2 only makes the derivative tidy; minimising J and minimising the MSE give the same theta.
    """
    residuals = predict(X, theta) - np.asarray(y, dtype=float)
    return float(residuals @ residuals / (2 * len(residuals)))


def gradient(X: np.ndarray, y: np.ndarray, theta: np.ndarray) -> np.ndarray:
    """The gradient of :func:`cost` with respect to theta: (1 / n) * X.T @ (X @ theta - y), shape ``(d,)``.

    Vectorised - no Python loop over examples or features.
    """
    X = np.asarray(X, dtype=float)
    residuals = X @ np.asarray(theta, dtype=float) - np.asarray(y, dtype=float)
    return X.T @ residuals / X.shape[0]


def normal_equation(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """The theta that minimises the cost in closed form - the solution of X.T X theta = X.T y.

    Must also work when X.T X is singular (a duplicated or perfectly collinear column): return the
    minimum-norm least-squares solution, as ``np.linalg.lstsq`` does, instead of raising. Don't invert X.T X.
    """
    theta, *_ = np.linalg.lstsq(np.asarray(X, dtype=float), np.asarray(y, dtype=float), rcond=None)
    return theta
