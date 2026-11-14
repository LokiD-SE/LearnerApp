"""Gradient descent for linear regression - batch, mini-batch and stochastic - plus feature scaling and a
diagnosis of the cost history.

The cost and gradient are those of ``linreg``: J(theta) = (1 / 2n) * sum((X @ theta - y)**2) and
grad = (1 / n) * X.T @ (X @ theta - y). ``X`` already includes the intercept column of ones.
"""

import numpy as np


def _cost(X: np.ndarray, y: np.ndarray, theta: np.ndarray) -> float:
    r = X @ theta - y
    return float(r @ r / (2 * len(r)))


def _gradient(X: np.ndarray, y: np.ndarray, theta: np.ndarray) -> np.ndarray:
    return X.T @ (X @ theta - y) / X.shape[0]


def batch_gradient_descent(
    X: np.ndarray, y: np.ndarray, lr: float, n_iters: int, theta0: np.ndarray | None = None
) -> tuple[np.ndarray, list[float]]:
    """Run ``n_iters`` steps of batch gradient descent: theta := theta - lr * gradient over ALL examples.

    Start from ``theta0`` (zeros if None). Return ``(theta, history)`` where ``history`` holds the cost before
    the first step and after every step - ``n_iters + 1`` floats. Keep going even if the cost becomes inf or
    nan (the history should show the divergence; ``np.errstate`` can silence overflow warnings).
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    theta = np.zeros(X.shape[1]) if theta0 is None else np.array(theta0, dtype=float)
    with np.errstate(over="ignore", invalid="ignore"):
        history = [_cost(X, y, theta)]
        for _ in range(n_iters):
            theta = theta - lr * _gradient(X, y, theta)
            history.append(_cost(X, y, theta))
    return theta, history


def minibatch_gradient_descent(
    X: np.ndarray, y: np.ndarray, lr: float, epochs: int, batch_size: int, seed: int = 0
) -> tuple[np.ndarray, list[float]]:
    """Mini-batch gradient descent from theta = zeros. ``batch_size=1`` is stochastic gradient descent and
    ``batch_size >= n`` is batch gradient descent.

    The exact procedure (the tests replay it):

    - ``rng = np.random.default_rng(seed)``, created once;
    - each epoch: ``order = rng.permutation(n)``; for ``start`` in ``range(0, n, batch_size)`` take
      ``idx = order[start:start + batch_size]`` and step theta := theta - lr * gradient on ``X[idx], y[idx]``
      (the gradient's 1/n uses the batch size, so it is the batch's mean);
    - ``history`` holds the cost on the FULL data before training and after every epoch - ``epochs + 1``
      floats.
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    n = X.shape[0]
    rng = np.random.default_rng(seed)
    theta = np.zeros(X.shape[1])
    with np.errstate(over="ignore", invalid="ignore"):
        history = [_cost(X, y, theta)]
        for _ in range(epochs):
            order = rng.permutation(n)
            for start in range(0, n, batch_size):
                idx = order[start : start + batch_size]
                theta = theta - lr * _gradient(X[idx], y[idx], theta)
            history.append(_cost(X, y, theta))
    return theta, history


def standardize(X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Scale every column to mean 0 and standard deviation 1 (population std, ``ddof=0``, like
    ``sklearn.preprocessing.StandardScaler``).

    Return ``(X_scaled, mean, std)``. A constant column (std 0) is left centred, not divided by zero: use a
    std of 1 for it. Do NOT pass the intercept column - add it after scaling.
    """
    X = np.asarray(X, dtype=float)
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std = np.where(std == 0, 1.0, std)
    return (X - mean) / std, mean, std


def unscale_theta(theta_scaled: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """Turn parameters learned on standardised features back into parameters for the ORIGINAL features.

    ``theta_scaled[0]`` is the intercept and ``theta_scaled[1:]`` the weights for (x - mean) / std. Return
    ``theta`` such that ``add_intercept(X) @ theta`` equals ``add_intercept(X_scaled) @ theta_scaled``:
    w = w_scaled / std and b = b_scaled - sum(w * mean).
    """
    theta_scaled = np.asarray(theta_scaled, dtype=float)
    weights = theta_scaled[1:] / np.asarray(std, dtype=float)
    intercept = theta_scaled[0] - float(weights @ np.asarray(mean, dtype=float))
    return np.concatenate([[intercept], weights])


def diagnose(history: list[float], tol: float = 1e-6) -> str:
    """Read a cost history and say what the learning rate did.

    In this order:

    - ``"diverged"`` - any value is inf or nan, or the last cost is larger than the first;
    - ``"converged"`` - the last step improved the cost by at most ``tol`` relative to the previous cost,
      that is ``(history[-2] - history[-1]) <= tol * history[-2]``;
    - ``"still-improving"`` - otherwise: more iterations (or a larger learning rate) would help.

    A history with fewer than two values raises ``ValueError``.
    """
    if len(history) < 2:
        raise ValueError("need at least two costs to diagnose")
    values = np.asarray(history, dtype=float)
    if not np.all(np.isfinite(values)) or values[-1] > values[0]:
        return "diverged"
    if values[-2] - values[-1] <= tol * values[-2]:
        return "converged"
    return "still-improving"
