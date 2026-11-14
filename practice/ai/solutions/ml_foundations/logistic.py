"""Logistic regression from scratch - reference solution. Exercise: exercises/ml_foundations/logistic.py.

Lesson: Logistic regression and classification (#/lesson/logistic-regression-classification).
X is an (n, d) float array of features, y an (n,) array of 0/1 labels (1 = fraud), w a (d,) weight vector
and b the intercept. Everything is vectorised - no Python loop over rows.
"""

import numpy as np


def sigmoid(z: np.ndarray) -> np.ndarray:
    """Return 1 / (1 + exp(-z)) element-wise, as floats, without overflow warnings for any finite z.

    sigmoid(-1000) is 0.0 and sigmoid(1000) is 1.0 - and NumPy must not print "overflow encountered in exp".
    """
    z = np.asarray(z, dtype=float)
    out = np.empty_like(z)
    pos = z >= 0
    # For z >= 0, exp(-z) <= 1 cannot overflow. For z < 0, rewrite as exp(z) / (1 + exp(z)), where
    # exp(z) < 1 cannot overflow either (it may underflow to 0.0, which is the right answer).
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    ez = np.exp(z[~pos])
    out[~pos] = ez / (1.0 + ez)
    return out


def log_loss_from_logits(z: np.ndarray, y: np.ndarray) -> float:
    """Return the mean binary cross-entropy (log loss) of logits z against labels y.

    Equal to mean(-y*log(sigmoid(z)) - (1-y)*log(1-sigmoid(z))), but computed from z directly so that it
    stays finite and accurate for very large |z|: a confident wrong logit of 1000 costs about 1000, not inf.
    """
    z = np.asarray(z, dtype=float)
    y = np.asarray(y, dtype=float)
    # -log sigmoid(z) = log(1 + e^-z) and -log(1 - sigmoid(z)) = log(1 + e^z); together softplus(z) - y*z.
    return float(np.mean(np.logaddexp(0.0, z) - y * z))


def gradient(X: np.ndarray, y: np.ndarray, w: np.ndarray, b: float, l2: float = 0.0) -> tuple[np.ndarray, float]:
    """Return (dJ/dw, dJ/db) for J = mean log loss + (l2 / 2) * ||w||^2. The intercept b is not penalised."""
    n = X.shape[0]
    error = sigmoid(X @ w + b) - y  # (p - y): the same shape as the linear-regression residual
    return X.T @ error / n + l2 * w, float(error.mean())


def fit_logistic(
    X: np.ndarray, y: np.ndarray, learning_rate: float = 0.5, n_iters: int = 2000, l2: float = 0.0
) -> tuple[np.ndarray, float]:
    """Fit w and b by batch gradient descent on J (see gradient), starting from zeros. Return (w, b)."""
    w = np.zeros(X.shape[1])
    b = 0.0
    for _ in range(n_iters):
        grad_w, grad_b = gradient(X, y, w, b, l2)
        w = w - learning_rate * grad_w
        b = b - learning_rate * grad_b
    return w, b


def predict_proba(X: np.ndarray, w: np.ndarray, b: float) -> np.ndarray:
    """Return P(y = 1 | x) for every row of X."""
    return sigmoid(X @ w + b)


def predict(X: np.ndarray, w: np.ndarray, b: float, threshold: float = 0.5) -> np.ndarray:
    """Return 1 where P(y = 1 | x) >= threshold, else 0, as an integer array."""
    return (predict_proba(X, w, b) >= threshold).astype(int)


def cost_threshold(cost_fp: float, cost_fn: float) -> float:
    """Return the probability threshold that minimises expected cost for calibrated probabilities.

    Flagging costs cost_fp if the transaction is genuine; not flagging costs cost_fn if it is fraud. Flag when
    p * cost_fn >= (1 - p) * cost_fp, i.e. when p >= cost_fp / (cost_fp + cost_fn).
    """
    return cost_fp / (cost_fp + cost_fn)


def best_threshold(probs: np.ndarray, y: np.ndarray, cost_fp: float, cost_fn: float) -> float:
    """Return the threshold, among the distinct values of probs, with the lowest total cost on (probs, y).

    A transaction is flagged when its probability is >= the threshold. Total cost = cost_fp * false
    positives + cost_fn * false negatives. On a tie, return the highest threshold (fewest flags).
    """
    probs = np.asarray(probs, dtype=float)
    y = np.asarray(y)
    candidates = np.unique(probs)  # sorted ascending
    flagged = probs[None, :] >= candidates[:, None]  # (n_candidates, n)
    fp = (flagged & (y == 0)).sum(axis=1)
    fn = (~flagged & (y == 1)).sum(axis=1)
    cost = cost_fp * fp + cost_fn * fn
    best = np.flatnonzero(cost == cost.min())[-1]  # the last minimum is the highest threshold
    return float(candidates[best])
