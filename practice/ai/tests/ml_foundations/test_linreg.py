"""Checks ml_foundations/linreg.py - the hypothesis, MSE, cost, gradient and the normal equation."""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from ml_foundations.linreg import add_intercept, cost, gradient, mse, normal_equation, predict

pytestmark = pytest.mark.exercise


def sandpay_fees(n: int = 200, seed: int = 7):
    """Synthetic SandPay data: monthly fee from transactions per month and average ticket."""
    rng = np.random.default_rng(seed)
    tx = rng.integers(200, 20000, n).astype(float)
    ticket = rng.uniform(5, 250, n).round(2)
    fee = 40 + 0.25 * tx + 1.8 * ticket + rng.normal(0, 60, n)
    return np.column_stack([tx, ticket]), fee


def test_add_intercept_prepends_a_column_of_ones_without_changing_the_input():
    X = np.array([[2, 3], [4, 5]])
    result = add_intercept(X)
    assert_allclose(result, [[1, 2, 3], [1, 4, 5]])
    assert result.dtype == float
    assert_allclose(X, [[2, 3], [4, 5]])


def test_add_intercept_turns_one_feature_vector_into_two_columns():
    assert_allclose(add_intercept(np.array([1.0, 2.0, 3.0])), [[1, 1], [1, 2], [1, 3]])


def test_predict_is_x_times_theta_for_every_row():
    X = np.array([[1.0, 2.0], [1.0, 5.0]])
    assert_allclose(predict(X, np.array([10.0, 3.0])), [16.0, 25.0])


def test_mse_is_the_mean_of_squared_errors():
    assert mse(np.array([3.0, 5.0, 7.0]), np.array([4.0, 5.0, 4.0])) == pytest.approx(10 / 3)
    assert isinstance(mse(np.array([1.0]), np.array([1.0])), float)


def test_mse_refuses_a_column_against_a_vector():
    # (3, 1) - (3,) broadcasts to a (3, 3) matrix: a silent, wrong answer
    with pytest.raises(ValueError):
        mse(np.array([1.0, 2.0, 3.0]), np.array([[1.0], [2.0], [3.0]]))


def test_cost_is_half_the_mean_squared_error():
    X, y = sandpay_fees()
    Xi = add_intercept(X)
    theta = np.array([10.0, 0.2, 1.0])
    assert cost(Xi, y, theta) == pytest.approx(mse(y, Xi @ theta) / 2)
    assert cost(Xi, y, np.zeros(3)) == pytest.approx(float(np.mean(y**2)) / 2)


def test_gradient_matches_a_numerical_derivative():
    X, y = sandpay_fees(n=30)
    Xi = add_intercept(X / [10000.0, 100.0])  # keep the numbers small for finite differences
    theta = np.array([5.0, -2.0, 3.0])
    eps = 1e-5
    numerical = np.array(
        [(cost(Xi, y, theta + eps * e) - cost(Xi, y, theta - eps * e)) / (2 * eps) for e in np.eye(3)]
    )
    assert_allclose(gradient(Xi, y, theta), numerical, rtol=1e-6)


def test_gradient_is_zero_at_the_least_squares_solution():
    X, y = sandpay_fees()
    Xi = add_intercept(X)
    theta = np.linalg.lstsq(Xi, y, rcond=None)[0]
    assert_allclose(gradient(Xi, y, theta), np.zeros(3), atol=1e-6)


def test_normal_equation_recovers_the_parameters_of_noise_free_data():
    X = np.array([[1, 1], [1, 2], [2, 2], [2, 3]], dtype=float)
    y = X @ np.array([1.0, 2.0]) + 3  # the scikit-learn LinearRegression docs example
    assert_allclose(normal_equation(add_intercept(X), y), [3.0, 1.0, 2.0], atol=1e-10)


def test_normal_equation_matches_scikit_learn_on_noisy_data():
    from sklearn.linear_model import LinearRegression

    X, y = sandpay_fees()
    model = LinearRegression().fit(X, y)
    expected = np.concatenate([[model.intercept_], model.coef_])
    assert_allclose(normal_equation(add_intercept(X), y), expected, rtol=1e-8)


def test_normal_equation_survives_a_duplicated_column():
    X, y = sandpay_fees()
    Xi = add_intercept(X)
    Xd = np.column_stack([Xi, Xi[:, 2]])  # X.T X is now singular
    theta = normal_equation(Xd, y)
    assert np.all(np.isfinite(theta))
    # the predictions are those of the full-rank fit, and the weight is shared equally (minimum norm)
    assert_allclose(Xd @ theta, Xi @ normal_equation(Xi, y), rtol=1e-8)
    assert theta[2] == pytest.approx(theta[3])
