"""Softmax (multinomial logistic) regression - exercise. Reference solution: solutions/ml_foundations/softmax.py.

Lesson: Logistic regression and classification (#/lesson/logistic-regression-classification).
logits is an (n, k) array of scores, one column per class; y is an (n,) array of integer labels 0..k-1.
Everything is vectorised and numerically stable - no Python loop over rows.
"""

import numpy as np


def softmax(logits: np.ndarray, axis: int = -1) -> np.ndarray:
    """Return exp(logits) normalised to sum to 1 along axis, without overflow for any finite logits.

    softmax([1000, 1001, 1002]) must equal softmax([0, 1, 2]) - not [nan, nan, nan].
    """
    # A first draft: the textbook formula. Run the tests to see where it breaks.
    e = np.exp(np.asarray(logits, dtype=float))
    return e / e.sum(axis=axis, keepdims=True)


def log_softmax(logits: np.ndarray, axis: int = -1) -> np.ndarray:
    """Return log(softmax(logits)) computed directly: logits - logsumexp(logits). Never -inf for finite input."""
    raise NotImplementedError


def cross_entropy(logits: np.ndarray, y: np.ndarray) -> float:
    """Return the mean cross-entropy -log softmax(logits)[i, y[i]] over the rows."""
    raise NotImplementedError


def cross_entropy_grad(logits: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Return d(cross_entropy)/d(logits), an (n, k) array: (softmax(logits) - one_hot(y)) / n."""
    raise NotImplementedError


def fit_softmax(
    X: np.ndarray, y: np.ndarray, n_classes: int, learning_rate: float = 0.5, n_iters: int = 2000
) -> tuple[np.ndarray, np.ndarray]:
    """Fit W (d, k) and b (k,) by batch gradient descent on the mean cross-entropy, from zeros. Return (W, b)."""
    raise NotImplementedError


def predict_proba(X: np.ndarray, W: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Return the (n, k) class probabilities softmax(X @ W + b); every row sums to 1."""
    raise NotImplementedError


def predict(X: np.ndarray, W: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Return the most probable class for every row (the largest logit - no softmax needed)."""
    raise NotImplementedError
