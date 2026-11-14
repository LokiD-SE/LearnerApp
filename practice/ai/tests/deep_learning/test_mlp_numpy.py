"""Tests for exercises/deep_learning/mlp_numpy.py (lesson: neural-networks-and-backprop).

The reference gradients come from PyTorch's autograd on the same network in float64, so a backward() that
agrees with your own numerical_gradients() but not with autograd is still caught.
"""

import warnings

import numpy as np
import pytest
import torch
from deep_learning.mlp_numpy import (
    PARAM_NAMES,
    backward,
    bce_with_logits,
    fit,
    forward,
    init_params,
    max_relative_error,
    numerical_gradients,
    predict,
    train_step,
)

pytestmark = pytest.mark.exercise


def small_problem(seed=0, n=12, d=3, h=4):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d))
    y = (rng.random(n) < 0.5).astype(float)
    params = init_params(d, h, rng)
    params["b1"] = rng.normal(0.0, 0.1, size=h)  # non-zero biases so their gradients are tested too
    params["b2"] = rng.normal(0.0, 0.1, size=1)
    return params, X, y


def xor_data(seed=3, n=200):
    """Synthetic SandPay-style data: fraud when exactly one of two standardised signals is high (XOR)."""
    rng = np.random.default_rng(seed)
    X = rng.uniform(-1.0, 1.0, size=(n, 2))
    X = X[np.abs(X).min(axis=1) > 0.1]  # a small margin around the axes
    y = ((X[:, 0] > 0) ^ (X[:, 1] > 0)).astype(float)
    return X, y


def autograd_gradients(params, X, y, activation):
    torch.manual_seed(0)
    t = {k: torch.tensor(v, dtype=torch.float64, requires_grad=True) for k, v in params.items()}
    Xt = torch.tensor(X, dtype=torch.float64)
    yt = torch.tensor(y, dtype=torch.float64)
    z1 = Xt @ t["W1"] + t["b1"]
    hidden = torch.tanh(z1) if activation == "tanh" else torch.relu(z1)
    logits = (hidden @ t["W2"] + t["b2"]).reshape(-1)
    loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, yt)
    loss.backward()
    return loss.item(), {k: t[k].grad.detach().numpy() for k in PARAM_NAMES}


def test_forward_returns_logits_and_the_cache_backward_needs():
    params, X, _ = small_problem()
    logits, cache = forward(params, X)
    assert logits.shape == (12,)
    assert cache["X"].shape == (12, 3)
    assert cache["Z1"].shape == (12, 4)
    assert cache["H"].shape == (12, 4)
    np.testing.assert_allclose(cache["H"], np.tanh(cache["Z1"]))
    np.testing.assert_allclose(cache["Z1"], X @ params["W1"] + params["b1"])
    relu_logits, relu_cache = forward(params, X, activation="relu")
    np.testing.assert_allclose(relu_cache["H"], np.maximum(0.0, relu_cache["Z1"]))
    assert relu_logits.shape == (12,)


def test_forward_rejects_inputs_of_the_wrong_shape():
    params, X, _ = small_problem()
    with pytest.raises(ValueError):
        forward(params, X[:, :2])
    with pytest.raises(ValueError):
        forward(params, X[0])


@pytest.mark.parametrize("activation", ["tanh", "relu"])
def test_bce_with_logits_matches_pytorch(activation):
    params, X, y = small_problem(seed=1)
    logits, _ = forward(params, X, activation)
    expected, _ = autograd_gradients(params, X, y, activation)
    assert bce_with_logits(logits, y) == pytest.approx(expected, rel=1e-12)


def test_bce_with_logits_is_finite_and_silent_for_confidently_wrong_logits():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        loss = bce_with_logits(np.array([1000.0, -1000.0, 40.0]), np.array([0.0, 1.0, 1.0]))
    # (1000 + 1000 + log(1 + e^-40)) / 3
    assert loss == pytest.approx(2000.0 / 3.0, rel=1e-12)


@pytest.mark.parametrize("activation", ["tanh", "relu"])
def test_backward_matches_autograd(activation):
    params, X, y = small_problem(seed=2)
    logits, cache = forward(params, X, activation)
    grads = backward(params, cache, logits, y, activation)
    _, expected = autograd_gradients(params, X, y, activation)
    assert set(grads) == set(PARAM_NAMES)
    for name in PARAM_NAMES:
        assert grads[name].shape == params[name].shape, name
        np.testing.assert_allclose(grads[name], expected[name], rtol=1e-9, atol=1e-12, err_msg=name)


def test_numerical_gradients_agree_with_autograd_and_leave_params_alone():
    params, X, y = small_problem(seed=4)
    before = {k: v.copy() for k, v in params.items()}
    numeric = numerical_gradients(params, X, y, "tanh")
    for name in PARAM_NAMES:
        np.testing.assert_array_equal(params[name], before[name], err_msg=f"{name} was changed")
    _, expected = autograd_gradients(params, X, y, "tanh")
    assert max_relative_error(numeric, expected) < 1e-6


def test_gradient_check_catches_a_wrong_backward():
    params, X, y = small_problem(seed=5)
    logits, cache = forward(params, X)
    grads = backward(params, cache, logits, y)
    numeric = numerical_gradients(params, X, y)
    assert max_relative_error(grads, numeric) < 1e-6
    broken = dict(grads, W1=grads["W1"] * 2.0)  # a classic slip: a factor of 2 in one layer
    assert max_relative_error(broken, numeric) > 0.3


def test_train_step_returns_new_arrays_and_the_loss_before_the_step():
    params, X, y = small_problem(seed=6)
    before = {k: v.copy() for k, v in params.items()}
    new_params, loss = train_step(params, X, y, learning_rate=0.5)
    for name in PARAM_NAMES:
        np.testing.assert_array_equal(params[name], before[name], err_msg=f"train_step changed params[{name!r}]")
        assert new_params[name] is not params[name]
    assert loss == pytest.approx(bce_with_logits(forward(before, X)[0], y))
    _, after = train_step(new_params, X, y, learning_rate=0.5)
    assert after < loss


def test_fit_learns_xor_which_no_linear_model_can():
    X, y = xor_data()
    params, losses = fit(X, y, n_hidden=8, learning_rate=0.5, epochs=1500, seed=0)
    assert losses[0] == pytest.approx(np.log(2), abs=0.05)  # small random weights: about 50/50
    assert losses[-1] < 0.1
    assert (predict(params, X) == y).mean() >= 0.98
