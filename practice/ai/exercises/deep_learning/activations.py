"""Activation functions and their derivatives - exercise. Reference solution: solutions/deep_learning/activations.py.

Lesson: Neural networks and backpropagation (#/lesson/neural-networks-and-backprop).
Every function works element-wise on an array of any shape and returns a float array of the same shape.
A "grad" function returns the local derivative d(activation)/dz at z - the factor backpropagation multiplies
by when the gradient passes back through the activation.
"""

import numpy as np


def sigmoid(z: np.ndarray) -> np.ndarray:
    """Return 1 / (1 + exp(-z)) without overflow warnings for large |z| (given, already correct)."""
    z = np.asarray(z, dtype=float)
    out = np.empty_like(z)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    e = np.exp(z[~pos])
    out[~pos] = e / (1.0 + e)
    return out


def sigmoid_grad(z: np.ndarray) -> np.ndarray:
    """Return the derivative of the sigmoid at z: sigmoid(z) * (1 - sigmoid(z)). Its largest value is 0.25, at 0."""
    # A colleague's draft. It looks like the textbook formula - run the tests to see why it isn't.
    z = np.asarray(z, dtype=float)
    return z * (1.0 - z)


def tanh_grad(z: np.ndarray) -> np.ndarray:
    """Return the derivative of tanh at z: 1 - tanh(z)**2. Its largest value is 1, at 0."""
    raise NotImplementedError


def relu(z: np.ndarray) -> np.ndarray:
    """Return max(0, z) element-wise (given, already correct)."""
    return np.maximum(0.0, np.asarray(z, dtype=float))


def relu_grad(z: np.ndarray) -> np.ndarray:
    """Return the derivative of ReLU: 1.0 where z > 0, else 0.0.

    ReLU has no derivative at exactly 0; like most libraries, use 0 there.
    """
    # A colleague's draft.
    return relu(z)


def leaky_relu(z: np.ndarray, alpha: float = 0.01) -> np.ndarray:
    """Return z where z > 0, else alpha * z."""
    raise NotImplementedError


def leaky_relu_grad(z: np.ndarray, alpha: float = 0.01) -> np.ndarray:
    """Return the derivative of leaky ReLU: 1.0 where z > 0, else alpha (alpha at exactly 0)."""
    raise NotImplementedError


def dead_relu_fraction(pre_activations: np.ndarray) -> float:
    """Return the fraction of hidden units that are "dead" on this batch.

    pre_activations is an (n, h) array of z = X @ W + b for n examples and h ReLU units. A unit is dead when
    its z is <= 0 for every example - its output and its gradient are then 0 on the whole batch, so gradient
    descent can't change its incoming weights. Raise ValueError if the array is not 2-D or has no rows.
    """
    raise NotImplementedError
