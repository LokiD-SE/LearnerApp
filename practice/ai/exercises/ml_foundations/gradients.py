"""Derivatives, gradients and gradient checking - exercise.

Lesson: The maths of machine learning (ml-maths-essentials).
Run: .venv/bin/python -m pytest tests/ml_foundations/test_gradients.py
"""

import numpy as np


def numerical_gradient(f, x, eps=1e-5):
    """Estimate the gradient of a scalar function f at the point x with centred differences.

    For each coordinate i:  (f(x + eps/2 * e_i) - f(x - eps/2 * e_i)) / eps
    where e_i is the i-th unit vector. x is a 1-D array; return a float array of the same shape.
    Do not change the caller's x.
    """
    # A first draft. It uses forward differences and nudges x in place - fix both.
    grad = np.zeros_like(x)
    for i in range(len(x)):
        before = f(x)
        x[i] += eps
        grad[i] = (f(x) - before) / eps
    return grad


def mse_loss_and_grad(X, y, w, b):
    """Mean squared error of the linear model X @ w + b, and its gradient.

    loss = mean((X @ w + b - y) ** 2)
    Return (loss, dw, db): loss and db are Python floats, dw is a 1-D array like w. Derive the gradient
    with the chain rule; do not estimate it numerically.
    """
    raise NotImplementedError


def gradient_check(f, grad, x, eps=1e-5):
    """Compare an analytic gradient with a numerical one at x and return the largest relative error.

    grad(x) returns the analytic gradient. For each coordinate:
        |analytic - numerical| / max(|analytic| + |numerical|, 1e-12)
    Return the maximum over coordinates as a Python float. A correct gradient gives a tiny number
    (around 1e-7 or less); a wrong one gives something far larger.
    """
    raise NotImplementedError
