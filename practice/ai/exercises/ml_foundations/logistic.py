"""Logistic regression from scratch - exercise. Reference solution: solutions/ml_foundations/logistic.py.

Lesson: Logistic regression and classification (#/lesson/logistic-regression-classification).
X is an (n, d) float array of features, y an (n,) array of 0/1 labels (1 = fraud), w a (d,) weight vector
and b the intercept. Everything is vectorised - no Python loop over rows.
"""

import numpy as np


def sigmoid(z: np.ndarray) -> np.ndarray:
    """Return 1 / (1 + exp(-z)) element-wise, as floats, without overflow warnings for any finite z.

    sigmoid(-1000) is 0.0 and sigmoid(1000) is 1.0 - and NumPy must not print "overflow encountered in exp".
    """
    # A first draft: run the tests and read which of them fail, and why.
    return 1 / (1 + np.exp(-np.asarray(z, dtype=float)))


def log_loss_from_logits(z: np.ndarray, y: np.ndarray) -> float:
    """Return the mean binary cross-entropy (log loss) of logits z against labels y.

    Equal to mean(-y*log(sigmoid(z)) - (1-y)*log(1-sigmoid(z))), but computed from z directly so that it
    stays finite and accurate for very large |z|: a confident wrong logit of 1000 costs about 1000, not inf.
    """
    # A first draft: correct on paper. Run the tests to see where it breaks.
    p = sigmoid(z)
    return float(np.mean(-y * np.log(p) - (1 - y) * np.log(1 - p)))


def gradient(X: np.ndarray, y: np.ndarray, w: np.ndarray, b: float, l2: float = 0.0) -> tuple[np.ndarray, float]:
    """Return (dJ/dw, dJ/db) for J = mean log loss + (l2 / 2) * ||w||^2. The intercept b is not penalised."""
    raise NotImplementedError


def fit_logistic(
    X: np.ndarray, y: np.ndarray, learning_rate: float = 0.5, n_iters: int = 2000, l2: float = 0.0
) -> tuple[np.ndarray, float]:
    """Fit w and b by batch gradient descent on J (see gradient), starting from zeros. Return (w, b)."""
    raise NotImplementedError


def predict_proba(X: np.ndarray, w: np.ndarray, b: float) -> np.ndarray:
    """Return P(y = 1 | x) for every row of X."""
    raise NotImplementedError


def predict(X: np.ndarray, w: np.ndarray, b: float, threshold: float = 0.5) -> np.ndarray:
    """Return 1 where P(y = 1 | x) >= threshold, else 0, as an integer array."""
    raise NotImplementedError


def cost_threshold(cost_fp: float, cost_fn: float) -> float:
    """Return the probability threshold that minimises expected cost for calibrated probabilities.

    Flagging costs cost_fp if the transaction is genuine; not flagging costs cost_fn if it is fraud. Flag when
    p * cost_fn >= (1 - p) * cost_fp, i.e. when p >= cost_fp / (cost_fp + cost_fn).
    """
    raise NotImplementedError


def best_threshold(probs: np.ndarray, y: np.ndarray, cost_fp: float, cost_fn: float) -> float:
    """Return the threshold, among the distinct values of probs, with the lowest total cost on (probs, y).

    A transaction is flagged when its probability is >= the threshold. Total cost = cost_fp * false
    positives + cost_fn * false negatives. On a tie, return the highest threshold (fewest flags).
    """
    raise NotImplementedError
