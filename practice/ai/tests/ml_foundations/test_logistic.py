"""Checks exercises/ml_foundations/logistic.py - lesson logistic-regression-classification."""

import warnings
from contextlib import contextmanager

import numpy as np
import pytest
from ml_foundations.logistic import (
    best_threshold,
    cost_threshold,
    fit_logistic,
    gradient,
    log_loss_from_logits,
    predict,
    predict_proba,
    sigmoid,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss

pytestmark = pytest.mark.exercise


def transactions(n=600, seed=3):
    """Synthetic SandPay transactions: 3 standardised features and a fraud label from a known model."""
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 3))
    z = X @ np.array([1.5, -1.0, 0.5]) - 1.0
    y = rng.binomial(1, 1 / (1 + np.exp(-z)))
    return X, y


@contextmanager
def no_numpy_warnings():
    """Inside this block any NumPy RuntimeWarning (overflow, divide by zero) fails the test."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        yield


class TestSigmoid:
    def test_known_values(self):
        np.testing.assert_allclose(sigmoid(np.array([0.0, 2.0, -2.0])), [0.5, 0.880797, 0.119203], atol=1e-6)

    def test_symmetry(self):
        z = np.linspace(-8, 8, 17)
        np.testing.assert_allclose(sigmoid(-z), 1 - sigmoid(z), atol=1e-12)

    def test_extreme_logits_without_overflow_warnings(self):
        with no_numpy_warnings():
            out = sigmoid(np.array([-1000.0, -40.0, 40.0, 1000.0]))
        assert out[0] == 0.0 and out[3] == 1.0
        assert 0 < out[1] < 1e-17, "sigmoid(-40) is about 4.2e-18, not exactly 0"

    def test_integer_input_gives_floats(self):
        assert sigmoid(np.array([0, 1])).dtype == np.float64


class TestLogLoss:
    def test_matches_scikit_learn_for_ordinary_logits(self):
        z = np.array([-2.0, -0.5, 0.0, 1.0, 3.0])
        y = np.array([0, 1, 0, 1, 1])
        p = 1 / (1 + np.exp(-z))
        assert log_loss_from_logits(z, y) == pytest.approx(log_loss(y, p))

    def test_confident_wrong_answer_costs_about_the_logit_not_inf(self):
        with no_numpy_warnings():
            loss = log_loss_from_logits(np.array([1000.0, -1000.0]), np.array([0, 1]))
        assert loss == pytest.approx(1000.0)

    def test_confident_right_answer_costs_almost_nothing(self):
        assert log_loss_from_logits(np.array([40.0, -40.0]), np.array([1, 0])) == pytest.approx(0.0, abs=1e-15)


class TestGradient:
    def test_matches_finite_differences(self):
        X, y = transactions(n=50)
        w, b, eps = np.array([0.3, -0.2, 0.1]), 0.05, 1e-6
        grad_w, grad_b = gradient(X, y, w, b, l2=0.1)

        def J(w_, b_):
            return log_loss_from_logits(X @ w_ + b_, y) + 0.05 * w_ @ w_

        numeric = [(J(w + eps * e, b) - J(w - eps * e, b)) / (2 * eps) for e in np.eye(3)]
        np.testing.assert_allclose(grad_w, numeric, atol=1e-6)
        assert grad_b == pytest.approx((J(w, b + eps) - J(w, b - eps)) / (2 * eps), abs=1e-6)

    def test_intercept_is_not_penalised(self):
        X, y = transactions(n=50)
        _, without = gradient(X, y, np.ones(3), 0.5, l2=0.0)
        _, with_l2 = gradient(X, y, np.ones(3), 0.5, l2=10.0)
        assert with_l2 == pytest.approx(without)


class TestFit:
    def test_unpenalised_fit_matches_scikit_learn(self):
        X, y = transactions()
        w, b = fit_logistic(X, y)
        ref = LogisticRegression(C=np.inf).fit(X, y)
        np.testing.assert_allclose(w, ref.coef_[0], atol=1e-3)
        assert b == pytest.approx(ref.intercept_[0], abs=1e-3)

    def test_l2_matches_scikit_learn_with_l2_equal_to_one_over_n_c(self):
        X, y = transactions()
        C = 0.05
        w, b = fit_logistic(X, y, l2=1 / (len(y) * C))
        ref = LogisticRegression(C=C).fit(X, y)
        np.testing.assert_allclose(w, ref.coef_[0], atol=1e-3)
        assert b == pytest.approx(ref.intercept_[0], abs=1e-3)

    def test_predict_proba_and_predict(self):
        X = np.array([[0.0, 0.0], [2.0, 0.0], [-2.0, 0.0]])
        w, b = np.array([1.0, 0.0]), 0.0
        np.testing.assert_allclose(predict_proba(X, w, b), [0.5, 0.880797, 0.119203], atol=1e-6)
        np.testing.assert_array_equal(predict(X, w, b), [1, 1, 0])
        np.testing.assert_array_equal(predict(X, w, b, threshold=0.9), [0, 0, 0])
        assert predict(X, w, b).dtype.kind == "i"


class TestThresholds:
    def test_cost_threshold(self):
        assert cost_threshold(cost_fp=4, cost_fn=120) == pytest.approx(4 / 124)
        assert cost_threshold(cost_fp=1, cost_fn=1) == pytest.approx(0.5)

    def test_best_threshold_minimises_total_cost(self):
        probs = np.array([0.02, 0.05, 0.10, 0.30, 0.60, 0.90])
        y = np.array([0, 0, 1, 0, 1, 1])
        # Flag >= 0.10 catches all three frauds with one false positive: cost 4.
        assert best_threshold(probs, y, cost_fp=4, cost_fn=120) == pytest.approx(0.10)
        # When missing a fraud is cheap, flag only the near-certain ones.
        assert best_threshold(probs, y, cost_fp=50, cost_fn=10) == pytest.approx(0.60)

    def test_ties_choose_the_highest_threshold(self):
        probs = np.array([0.1, 0.2, 0.8])
        y = np.array([1, 0, 1])
        # Every threshold costs 1 (one false positive at 0.1, one missed fraud at 0.2 and at 0.8).
        assert best_threshold(probs, y, cost_fp=1, cost_fn=1) == pytest.approx(0.8)
