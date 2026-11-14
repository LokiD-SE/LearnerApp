"""Checks ml_foundations/gradient_descent.py - batch and mini-batch descent, scaling and diagnosis."""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from ml_foundations.gradient_descent import (
    batch_gradient_descent,
    diagnose,
    minibatch_gradient_descent,
    standardize,
    unscale_theta,
)

pytestmark = pytest.mark.exercise


def sandpay_fees(n: int = 200, seed: int = 7):
    rng = np.random.default_rng(seed)
    tx = rng.integers(200, 20000, n).astype(float)
    ticket = rng.uniform(5, 250, n).round(2)
    fee = 40 + 0.25 * tx + 1.8 * ticket + rng.normal(0, 60, n)
    return np.column_stack([tx, ticket]), fee


def with_ones(X):
    return np.column_stack([np.ones(len(X)), X])


def least_squares(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


@pytest.fixture
def scaled():
    X, y = sandpay_fees()
    Xs, mean, std = standardize(X)
    return X, with_ones(Xs), y, mean, std


def test_one_step_by_hand():
    X = np.array([[1.0, 1.0], [1.0, 2.0], [1.0, 3.0]])
    y = np.array([2.0, 4.0, 6.0])
    theta, history = batch_gradient_descent(X, y, lr=0.1, n_iters=1)
    # gradient at zero = (1/3) * X.T @ (0 - y) = [-4, -28/3]
    assert_allclose(theta, [0.4, 28 / 30])
    assert history[0] == pytest.approx((4 + 16 + 36) / 6)
    assert len(history) == 2


def test_history_has_the_starting_cost_and_one_cost_per_step(scaled):
    _, Xsi, y, _, _ = scaled
    _, history = batch_gradient_descent(Xsi, y, lr=0.1, n_iters=25)
    assert len(history) == 26
    assert all(later <= earlier for earlier, later in zip(history, history[1:]))


def test_starts_from_theta0_when_given():
    X = np.array([[1.0, 0.0], [1.0, 1.0]])
    y = np.array([1.0, 3.0])
    theta, history = batch_gradient_descent(X, y, lr=0.5, n_iters=0, theta0=np.array([1.0, 2.0]))
    assert_allclose(theta, [1.0, 2.0])
    assert history == [pytest.approx(0.0)]


def test_a_good_learning_rate_reaches_the_least_squares_solution(scaled):
    _, Xsi, y, _, _ = scaled
    theta, _ = batch_gradient_descent(Xsi, y, lr=0.5, n_iters=200)
    assert_allclose(theta, least_squares(Xsi, y), rtol=1e-6)


def test_too_large_a_learning_rate_diverges_and_the_history_shows_it(scaled):
    _, Xsi, y, _, _ = scaled
    _, history = batch_gradient_descent(Xsi, y, lr=2.1, n_iters=200)
    assert len(history) == 201
    assert history[-1] > history[0] * 1e6


def test_standardize_gives_mean_zero_and_std_one_like_standard_scaler():
    from sklearn.preprocessing import StandardScaler

    X, _ = sandpay_fees()
    Xs, mean, std = standardize(X)
    scaler = StandardScaler().fit(X)
    assert_allclose(Xs, scaler.transform(X), atol=1e-12)
    assert_allclose(mean, scaler.mean_)
    assert_allclose(std, scaler.scale_)


def test_standardize_leaves_a_constant_column_centred_instead_of_dividing_by_zero():
    X = np.array([[1.0, 5.0], [2.0, 5.0], [3.0, 5.0]])
    Xs, _, std = standardize(X)
    assert np.all(np.isfinite(Xs))
    assert_allclose(Xs[:, 1], 0.0)
    assert std[1] == 1.0


def test_unscale_theta_gives_parameters_for_the_original_features(scaled):
    X, Xsi, y, mean, std = scaled
    theta_scaled = least_squares(Xsi, y)
    theta = unscale_theta(theta_scaled, mean, std)
    assert_allclose(theta, least_squares(with_ones(X), y), rtol=1e-8)
    assert_allclose(with_ones(X) @ theta, Xsi @ theta_scaled, rtol=1e-10)


def test_minibatch_with_the_whole_data_is_batch_gradient_descent(scaled):
    _, Xsi, y, _, _ = scaled
    theta_mb, history_mb = minibatch_gradient_descent(Xsi, y, lr=0.1, epochs=30, batch_size=len(y), seed=3)
    theta_b, history_b = batch_gradient_descent(Xsi, y, lr=0.1, n_iters=30)
    assert_allclose(theta_mb, theta_b, rtol=1e-12)
    assert_allclose(history_mb, history_b, rtol=1e-12)


def test_minibatch_follows_the_specified_shuffle(scaled):
    _, Xsi, y, _, _ = scaled
    theta, history = minibatch_gradient_descent(Xsi, y, lr=0.05, epochs=3, batch_size=16, seed=11)
    # replay the procedure from the docstring
    rng = np.random.default_rng(11)
    expected = np.zeros(3)
    for _ in range(3):
        order = rng.permutation(len(y))
        for start in range(0, len(y), 16):
            idx = order[start : start + 16]
            Xb, yb = Xsi[idx], y[idx]
            expected = expected - 0.05 * Xb.T @ (Xb @ expected - yb) / len(idx)
    assert_allclose(theta, expected, rtol=1e-12)
    assert len(history) == 4


def test_sgd_gets_close_in_a_few_epochs_but_keeps_moving(scaled):
    _, Xsi, y, _, _ = scaled
    best = least_squares(Xsi, y)
    optimum = float(np.mean((Xsi @ best - y) ** 2)) / 2
    _, history = minibatch_gradient_descent(Xsi, y, lr=0.01, epochs=10, batch_size=1, seed=0)
    assert history[5] < optimum * 1.01  # close after 5 epochs...
    assert history[10] > optimum  # ...but a constant step never settles exactly on the minimum


@pytest.mark.parametrize(
    "history, expected",
    [
        ([10.0, 4.0, 2.0, 1.0], "still-improving"),
        ([10.0, 4.0, 2.0, 2.0], "converged"),
        ([10.0, 4.0, 2.0, 1.9999999], "converged"),
        ([10.0, 30.0, 90.0], "diverged"),
        ([10.0, 4.0, float("nan")], "diverged"),
        ([10.0, 4.0, float("inf")], "diverged"),
        ([10.0, 12.0, 11.0], "diverged"),
        ([10.0, 12.0, 9.0], "still-improving"),
    ],
)
def test_diagnose(history, expected):
    assert diagnose(history) == expected


def test_diagnose_respects_tol_and_needs_two_values():
    assert diagnose([10.0, 5.0, 4.9], tol=0.05) == "converged"
    assert diagnose([10.0, 5.0, 4.9], tol=0.01) == "still-improving"
    with pytest.raises(ValueError):
        diagnose([1.0])


def test_diagnose_spots_an_unscaled_learning_rate_that_is_too_small():
    X, y = sandpay_fees()
    _, history = batch_gradient_descent(with_ones(X), y, lr=1e-8, n_iters=1000)
    assert diagnose(history) == "still-improving"
    best = least_squares(with_ones(X), y)
    optimum = float(np.mean((with_ones(X) @ best - y) ** 2)) / 2
    assert history[-1] > 9 * optimum  # after 1000 steps, still nowhere near the optimum
