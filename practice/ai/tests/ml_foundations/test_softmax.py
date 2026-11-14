"""Checks exercises/ml_foundations/softmax.py - lesson logistic-regression-classification."""

import warnings

import numpy as np
import pytest
from ml_foundations.softmax import (
    cross_entropy,
    cross_entropy_grad,
    fit_softmax,
    log_softmax,
    predict,
    predict_proba,
    softmax,
)
from sklearn.linear_model import LogisticRegression

pytestmark = pytest.mark.exercise


def disputes(n=600, seed=5):
    """Synthetic SandPay disputes: 2 standardised features, 3 reasons (0 fraud, 1 not received, 2 duplicate)."""
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 2))
    logits = X @ np.array([[1.0, -1.0, 0.0], [0.0, 1.0, -1.0]]) + np.array([0.2, 0.0, -0.5])
    p = np.exp(logits - logits.max(axis=1, keepdims=True))
    p /= p.sum(axis=1, keepdims=True)
    y = (rng.random(n)[:, None] > np.cumsum(p, axis=1)).sum(axis=1)
    return X, y


class TestSoftmax:
    def test_known_values_and_rows_sum_to_one(self):
        out = softmax(np.array([[1.0, 2.0, 3.0], [0.0, 0.0, 0.0]]))
        np.testing.assert_allclose(out[0], [0.090031, 0.244728, 0.665241], atol=1e-6)
        np.testing.assert_allclose(out[1], [1 / 3] * 3)
        np.testing.assert_allclose(out.sum(axis=1), [1.0, 1.0])

    def test_large_logits_do_not_overflow(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            out = softmax(np.array([1000.0, 1001.0, 1002.0]))
        np.testing.assert_allclose(out, softmax(np.array([0.0, 1.0, 2.0])))

    def test_axis_argument(self):
        logits = np.array([[1.0, 5.0], [3.0, 1.0]])
        np.testing.assert_allclose(softmax(logits, axis=0).sum(axis=0), [1.0, 1.0])

    def test_does_not_change_its_input(self):
        logits = np.array([[3.0, 1.0, 2.0]])
        before = logits.copy()
        softmax(logits)
        np.testing.assert_array_equal(logits, before)


class TestLogSoftmax:
    def test_equals_log_of_softmax_for_ordinary_logits(self):
        logits = np.array([[1.0, 2.0, 3.0], [-1.0, 0.5, 4.0]])
        np.testing.assert_allclose(log_softmax(logits), np.log(softmax(logits)))

    def test_stays_finite_where_softmax_underflows(self):
        out = log_softmax(np.array([0.0, -1000.0]))
        assert np.isfinite(out).all()
        assert out[1] == pytest.approx(-1000.0)


class TestCrossEntropy:
    def test_value(self):
        logits = np.array([[2.0, 1.0, 0.1], [0.5, 2.5, 0.3]])
        y = np.array([0, 1])
        expected = -np.mean([np.log(softmax(logits[0])[0]), np.log(softmax(logits[1])[1])])
        assert cross_entropy(logits, y) == pytest.approx(expected)

    def test_confident_wrong_answer_is_finite(self):
        assert cross_entropy(np.array([[1000.0, 0.0]]), np.array([1])) == pytest.approx(1000.0)

    def test_gradient_matches_finite_differences(self):
        rng = np.random.default_rng(0)
        logits, y, eps = rng.normal(size=(4, 3)), np.array([0, 2, 1, 2]), 1e-6
        numeric = np.zeros_like(logits)
        for idx in np.ndindex(*logits.shape):
            step = np.zeros_like(logits)
            step[idx] = eps
            numeric[idx] = (cross_entropy(logits + step, y) - cross_entropy(logits - step, y)) / (2 * eps)
        np.testing.assert_allclose(cross_entropy_grad(logits, y), numeric, atol=1e-6)

    def test_gradient_rows_sum_to_zero(self):
        grad = cross_entropy_grad(np.array([[1.0, 2.0, 3.0]]), np.array([2]))
        assert grad.sum() == pytest.approx(0.0)


class TestFit:
    def test_probabilities_match_unpenalised_scikit_learn(self):
        X, y = disputes()
        W, b = fit_softmax(X, y, n_classes=3)
        ref = LogisticRegression(C=np.inf).fit(X, y)
        # The weights are not unique (adding the same vector to every class changes nothing), but the
        # probabilities are - compare those.
        np.testing.assert_allclose(predict_proba(X, W, b), ref.predict_proba(X), atol=1e-3)
        np.testing.assert_array_equal(predict(X, W, b), ref.predict(X))

    def test_shapes(self):
        X, y = disputes(n=60)
        W, b = fit_softmax(X, y, n_classes=3, n_iters=10)
        assert W.shape == (2, 3) and b.shape == (3,)
        assert predict_proba(X, W, b).shape == (60, 3)
