"""Checks exercises/ml_foundations/gradients.py (lesson ml-maths-essentials)."""

import numpy as np
import pytest
from ml_foundations.gradients import gradient_check, mse_loss_and_grad, numerical_gradient

pytestmark = pytest.mark.exercise


def cube_sum(x):
    return float(np.sum(x**3))


def regression_data():
    rng = np.random.default_rng(7)
    X = rng.normal(size=(50, 3))
    y = X @ np.array([2.0, -1.0, 0.5]) + 0.3 + rng.normal(scale=0.1, size=50)
    return X, y


class TestNumericalGradient:
    def test_matches_the_derivative_of_a_cube(self):
        # d/dx x^3 = 3x^2; centred differences are accurate to about 1e-9 here
        x = np.array([2.0, -1.0, 0.5])
        np.testing.assert_allclose(numerical_gradient(cube_sum, x), 3 * x**2, rtol=1e-8)

    def test_is_centred_not_forward(self):
        # With a large eps, forward differences are off by 3x*eps + eps^2; centred ones by eps^2 / 4.
        x = np.array([2.0])
        assert numerical_gradient(cube_sum, x, eps=0.1)[0] == pytest.approx(12.0025)

    def test_works_for_integer_input(self):
        np.testing.assert_allclose(numerical_gradient(cube_sum, np.array([1, 2])), [3.0, 12.0], rtol=1e-8)

    def test_does_not_change_the_callers_array(self):
        x = np.array([2.0, -1.0])
        numerical_gradient(cube_sum, x)
        np.testing.assert_array_equal(x, [2.0, -1.0])

    def test_gradient_of_a_quadratic_form(self):
        # For symmetric A, the gradient of x^T A x is 2 A x (CS229 linear algebra review, 4.3)
        A = np.array([[2.0, 1.0], [1.0, 3.0]])
        x = np.array([1.0, 2.0])
        np.testing.assert_allclose(numerical_gradient(lambda v: v @ A @ v, x), [8.0, 14.0], rtol=1e-7)


class TestMseLossAndGrad:
    def test_loss_at_zero_weights(self):
        X, y = regression_data()
        loss, dw, db = mse_loss_and_grad(X, y, np.zeros(3), 0.0)
        assert loss == pytest.approx(np.mean(y**2))
        assert type(loss) is float and type(db) is float
        assert dw.shape == (3,)

    def test_gradient_matches_finite_differences(self):
        X, y = regression_data()
        w = np.array([0.5, 0.5, 0.5])
        _, dw, db = mse_loss_and_grad(X, y, w, 0.1)
        num_dw = numerical_gradient(lambda v: mse_loss_and_grad(X, y, v, 0.1)[0], w)
        num_db = numerical_gradient(lambda v: mse_loss_and_grad(X, y, w, v[0])[0], np.array([0.1]))[0]
        np.testing.assert_allclose(dw, num_dw, rtol=1e-6)
        assert db == pytest.approx(num_db, rel=1e-6)

    def test_known_values(self):
        X = np.array([[1.0, 0.0], [0.0, 1.0]])
        y = np.array([1.0, 2.0])
        loss, dw, db = mse_loss_and_grad(X, y, np.array([0.0, 0.0]), 0.0)
        assert loss == pytest.approx(2.5)  # (1 + 4) / 2
        np.testing.assert_allclose(dw, [-1.0, -2.0])  # 2/2 * X^T (-y)
        assert db == pytest.approx(-3.0)

    def test_gradient_is_zero_at_an_exact_fit(self):
        X = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 7.0]])
        w = np.array([0.5, -1.0])
        y = X @ w + 2.0
        loss, dw, db = mse_loss_and_grad(X, y, w, 2.0)
        assert loss == pytest.approx(0.0, abs=1e-20)
        np.testing.assert_allclose(dw, 0.0, atol=1e-12)
        assert db == pytest.approx(0.0, abs=1e-12)

    def test_descending_the_gradient_lowers_the_loss(self):
        X, y = regression_data()
        w, b = np.zeros(3), 0.0
        first = mse_loss_and_grad(X, y, w, b)[0]
        for _ in range(50):
            _, dw, db = mse_loss_and_grad(X, y, w, b)
            w, b = w - 0.1 * dw, b - 0.1 * db
        last = mse_loss_and_grad(X, y, w, b)[0]
        assert last < 0.01 < first
        np.testing.assert_allclose(w, [2.0, -1.0, 0.5], atol=0.05)


class TestGradientCheck:
    def test_a_correct_gradient_passes(self):
        x = np.array([2.0, -1.0, 0.5])
        assert gradient_check(cube_sum, lambda v: 3 * v**2, x) < 1e-7

    def test_a_gradient_missing_a_factor_fails(self):
        # Forgetting the 3 from d/dx x^3 = 3x^2: relative error (3 - 1) / (3 + 1) = 0.5
        x = np.array([2.0, -1.0, 0.5])
        assert gradient_check(cube_sum, lambda v: v**2, x) == pytest.approx(0.5, rel=1e-6)

    def test_reports_the_worst_coordinate(self):
        # Only the second coordinate is wrong (sign flipped): relative error 1.0
        x = np.array([2.0, -1.0, 0.5])
        assert gradient_check(cube_sum, lambda v: 3 * v**2 * np.array([1.0, -1.0, 1.0]), x) == pytest.approx(1.0)

    def test_returns_a_python_float(self):
        assert type(gradient_check(cube_sum, lambda v: 3 * v**2, np.array([1.0]))) is float

    def test_zero_gradient_does_not_divide_by_zero(self):
        assert gradient_check(lambda v: 5.0, lambda v: np.zeros_like(v), np.array([1.0, 2.0])) == 0.0
