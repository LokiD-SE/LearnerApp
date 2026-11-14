"""Derivatives, gradients and gradient checking - reference solution.

Lesson: The maths of machine learning (ml-maths-essentials).
"""

import numpy as np


def numerical_gradient(f, x, eps=1e-5):
    """Estimate the gradient of a scalar function f at the point x with centred differences.

    For each coordinate i:  (f(x + eps/2 * e_i) - f(x - eps/2 * e_i)) / eps
    where e_i is the i-th unit vector. x is a 1-D array; return a float array of the same shape.
    Do not change the caller's x.
    """
    x = np.array(x, dtype=float)  # a copy: the caller's array is never touched
    grad = np.zeros_like(x)
    for i in range(x.size):
        step = np.zeros_like(x)
        step[i] = eps / 2
        grad[i] = (f(x + step) - f(x - step)) / eps
    return grad


def mse_loss_and_grad(X, y, w, b):
    """Mean squared error of the linear model X @ w + b, and its gradient.

    loss = mean((X @ w + b - y) ** 2)
    Return (loss, dw, db): loss and db are Python floats, dw is a 1-D array like w. Derive the gradient
    with the chain rule; do not estimate it numerically.
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    w = np.asarray(w, dtype=float)
    n = len(y)
    residual = X @ w + b - y  # inner function r(w, b)
    loss = float(np.mean(residual**2))  # outer function mean(r^2)
    # chain rule: d loss / d r = 2 r / n, d r / d w = X, d r / d b = 1
    dw = (2 / n) * X.T @ residual
    db = float((2 / n) * residual.sum())
    return loss, dw, db


def gradient_check(f, grad, x, eps=1e-5):
    """Compare an analytic gradient with a numerical one at x and return the largest relative error.

    grad(x) returns the analytic gradient. For each coordinate:
        |analytic - numerical| / max(|analytic| + |numerical|, 1e-12)
    Return the maximum over coordinates as a Python float. A correct gradient gives a tiny number
    (around 1e-7 or less); a wrong one gives something far larger.
    """
    analytic = np.asarray(grad(np.array(x, dtype=float)), dtype=float)
    numerical = numerical_gradient(f, x, eps)
    denominator = np.maximum(np.abs(analytic) + np.abs(numerical), 1e-12)
    return float(np.max(np.abs(analytic - numerical) / denominator))
