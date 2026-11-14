"""Softmax (multinomial logistic) regression - reference solution. Exercise: exercises/ml_foundations/softmax.py.

Lesson: Logistic regression and classification (#/lesson/logistic-regression-classification).
logits is an (n, k) array of scores, one column per class; y is an (n,) array of integer labels 0..k-1.
Everything is vectorised and numerically stable - no Python loop over rows.
"""

import numpy as np


def softmax(logits: np.ndarray, axis: int = -1) -> np.ndarray:
    """Return exp(logits) normalised to sum to 1 along axis, without overflow for any finite logits.

    softmax([1000, 1001, 1002]) must equal softmax([0, 1, 2]) - not [nan, nan, nan].
    """
    logits = np.asarray(logits, dtype=float)
    # Subtracting the maximum does not change the result (softmax is shift-invariant) and makes the
    # largest exponent exp(0) = 1: no overflow, and the denominator is at least 1.
    shifted = logits - logits.max(axis=axis, keepdims=True)
    e = np.exp(shifted)
    return e / e.sum(axis=axis, keepdims=True)


def log_softmax(logits: np.ndarray, axis: int = -1) -> np.ndarray:
    """Return log(softmax(logits)) computed directly: logits - logsumexp(logits). Never -inf for finite input."""
    logits = np.asarray(logits, dtype=float)
    m = logits.max(axis=axis, keepdims=True)
    log_sum_exp = m + np.log(np.exp(logits - m).sum(axis=axis, keepdims=True))
    return logits - log_sum_exp


def cross_entropy(logits: np.ndarray, y: np.ndarray) -> float:
    """Return the mean cross-entropy -log softmax(logits)[i, y[i]] over the rows."""
    logp = log_softmax(logits, axis=1)
    return float(-logp[np.arange(len(y)), y].mean())


def cross_entropy_grad(logits: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Return d(cross_entropy)/d(logits), an (n, k) array: (softmax(logits) - one_hot(y)) / n."""
    n = logits.shape[0]
    grad = softmax(logits, axis=1)
    grad[np.arange(n), y] -= 1.0
    return grad / n


def fit_softmax(
    X: np.ndarray, y: np.ndarray, n_classes: int, learning_rate: float = 0.5, n_iters: int = 2000
) -> tuple[np.ndarray, np.ndarray]:
    """Fit W (d, k) and b (k,) by batch gradient descent on the mean cross-entropy, from zeros. Return (W, b)."""
    W = np.zeros((X.shape[1], n_classes))
    b = np.zeros(n_classes)
    for _ in range(n_iters):
        g = cross_entropy_grad(X @ W + b, y)  # (n, k), already divided by n
        W = W - learning_rate * (X.T @ g)
        b = b - learning_rate * g.sum(axis=0)
    return W, b


def predict_proba(X: np.ndarray, W: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Return the (n, k) class probabilities softmax(X @ W + b); every row sums to 1."""
    return softmax(X @ W + b, axis=1)


def predict(X: np.ndarray, W: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Return the most probable class for every row (the largest logit - no softmax needed)."""
    return np.argmax(X @ W + b, axis=1)
