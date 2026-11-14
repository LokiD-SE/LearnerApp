"""Tests for exercises/deep_learning/activations.py (lesson: neural-networks-and-backprop)."""

import warnings

import numpy as np
import pytest
from deep_learning.activations import (
    dead_relu_fraction,
    leaky_relu,
    leaky_relu_grad,
    relu,
    relu_grad,
    sigmoid,
    sigmoid_grad,
    tanh_grad,
)

pytestmark = pytest.mark.exercise

# Points away from 0, so the centred difference never straddles the ReLU kink.
Z = np.array([-6.0, -2.5, -0.7, -0.1, 0.1, 0.7, 2.5, 6.0])


def centred_difference(f, z, eps=1e-6):
    return (f(z + eps / 2) - f(z - eps / 2)) / eps


def test_sigmoid_grad_matches_a_numerical_derivative():
    np.testing.assert_allclose(sigmoid_grad(Z), centred_difference(sigmoid, Z), rtol=1e-6, atol=1e-10)


def test_sigmoid_grad_peaks_at_a_quarter_and_vanishes_in_the_tails():
    assert sigmoid_grad(np.array([0.0]))[0] == pytest.approx(0.25)
    assert sigmoid_grad(np.array([10.0]))[0] == pytest.approx(4.5398e-05, rel=1e-4)
    assert sigmoid_grad(np.array([-10.0]))[0] == pytest.approx(4.5398e-05, rel=1e-4)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = sigmoid_grad(np.array([-1000.0, 1000.0]))
    np.testing.assert_allclose(out, [0.0, 0.0], atol=1e-300)


def test_tanh_grad_matches_a_numerical_derivative_and_peaks_at_one():
    np.testing.assert_allclose(tanh_grad(Z), centred_difference(np.tanh, Z), rtol=1e-6, atol=1e-10)
    assert tanh_grad(np.array([0.0]))[0] == pytest.approx(1.0)


def test_relu_grad_is_a_step_with_zero_at_the_kink():
    z = np.array([-3.0, -1e-9, 0.0, 1e-9, 2.0, 50.0])
    np.testing.assert_array_equal(relu_grad(z), [0.0, 0.0, 0.0, 1.0, 1.0, 1.0])
    np.testing.assert_allclose(relu_grad(Z), centred_difference(relu, Z), atol=1e-6)


def test_leaky_relu_and_its_gradient():
    z = np.array([-200.0, -1.0, 0.0, 3.0])
    np.testing.assert_allclose(leaky_relu(z), [-2.0, -0.01, 0.0, 3.0])
    np.testing.assert_allclose(leaky_relu(z, alpha=0.2), [-40.0, -0.2, 0.0, 3.0])
    np.testing.assert_allclose(leaky_relu_grad(z), [0.01, 0.01, 0.01, 1.0])
    np.testing.assert_allclose(
        leaky_relu_grad(Z, alpha=0.1), centred_difference(lambda v: leaky_relu(v, 0.1), Z), atol=1e-6
    )


def test_every_function_keeps_the_shape_and_returns_floats():
    z = np.arange(-6, 6).reshape(3, 4)  # integers on purpose
    for f in (sigmoid_grad, tanh_grad, relu_grad, leaky_relu, leaky_relu_grad):
        out = f(z)
        assert out.shape == (3, 4), f.__name__
        assert out.dtype == np.float64, f.__name__


def test_dead_relu_fraction_counts_units_that_never_fire_on_the_batch():
    z = np.array(
        [
            [-1.0, 0.5, 0.0, -2.0],
            [-0.5, -1.0, -3.0, -0.1],
            [-2.0, -0.2, -1.0, 4.0],
        ]
    )
    # unit 0 and unit 2 never exceed 0 (0.0 is not firing); units 1 and 3 fire on one example each
    assert dead_relu_fraction(z) == pytest.approx(0.5)
    assert dead_relu_fraction(np.ones((2, 5))) == 0.0
    assert dead_relu_fraction(-np.ones((2, 5))) == 1.0


def test_dead_relu_fraction_rejects_bad_shapes():
    with pytest.raises(ValueError):
        dead_relu_fraction(np.array([1.0, -1.0]))
    with pytest.raises(ValueError):
        dead_relu_fraction(np.zeros((0, 3)))
