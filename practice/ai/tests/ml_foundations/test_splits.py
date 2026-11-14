"""Checks exercises/ml_foundations/splits.py: stratified and group splits, and fitting without leakage."""

import numpy as np
import pytest
from sklearn.metrics import average_precision_score
from sklearn.pipeline import Pipeline

from ml_foundations.splits import fit_and_score, group_split, stratified_split

pytestmark = pytest.mark.exercise


def labels(n=1000, fraud=12):
    y = np.zeros(n, dtype=int)
    y[np.random.default_rng(0).choice(n, fraud, replace=False)] = 1
    return y


def assert_partition(train, test, n):
    assert isinstance(train, np.ndarray) and isinstance(test, np.ndarray)
    assert np.array_equal(train, np.sort(train)) and np.array_equal(test, np.sort(test))
    assert np.intersect1d(train, test).size == 0
    assert np.array_equal(np.sort(np.concatenate([train, test])), np.arange(n))


def test_stratified_split_is_a_partition():
    train, test = stratified_split(labels(), 0.25, seed=1)
    assert_partition(train, test, 1000)


def test_stratified_split_keeps_each_class_share():
    y = labels(1000, 12)
    for seed in range(10):
        _, test = stratified_split(y, 0.25, seed=seed)
        assert y[test].sum() == 3  # round(12 * 0.25), on every seed
        assert len(test) == 3 + round(988 * 0.25)


def test_stratified_split_is_random_but_repeatable():
    y = labels()
    a = stratified_split(y, 0.2, seed=5)[1]
    b = stratified_split(y, 0.2, seed=5)[1]
    c = stratified_split(y, 0.2, seed=6)[1]
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)
    # Chosen at random, not simply the first rows of each class.
    first_rows = np.sort(np.concatenate([np.flatnonzero(y == k)[: np.sum(y[a] == k)] for k in (0, 1)]))
    assert not np.array_equal(a, first_rows)


@pytest.mark.parametrize("bad", [0, 1, -0.2, 1.5])
def test_stratified_split_rejects_bad_fractions(bad):
    with pytest.raises(ValueError):
        stratified_split(labels(), bad, seed=0)


def test_group_split_never_shares_a_merchant():
    merchants = np.random.default_rng(2).integers(0, 40, 3000)
    train, test = group_split(merchants, 0.2, seed=3)
    assert_partition(train, test, 3000)
    assert np.intersect1d(merchants[train], merchants[test]).size == 0
    assert len(np.unique(merchants[test])) == round(40 * 0.2)


def test_group_split_is_repeatable_and_keeps_both_sides_non_empty():
    merchants = np.array(["m1", "m1", "m2", "m3", "m3", "m3"])
    a = group_split(merchants, 0.01, seed=0)
    assert len(np.unique(merchants[a[1]])) == 1  # at least one group in test
    b = group_split(merchants, 0.99, seed=0)
    assert len(np.unique(merchants[b[0]])) == 1  # never every group in test
    assert np.array_equal(group_split(merchants, 0.5, seed=9)[1], group_split(merchants, 0.5, seed=9)[1])


def test_group_split_rejects_a_single_group_and_bad_fractions():
    with pytest.raises(ValueError):
        group_split(np.array([7, 7, 7]), 0.3, seed=0)
    with pytest.raises(ValueError):
        group_split(np.array([1, 2, 3]), 1.0, seed=0)


def fraud_data(seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(600, 4)) * [1, 10, 100, 0.5] + [0, 50, 500, 2]
    y = (X[:, 0] + 0.05 * X[:, 1] + rng.normal(0, 1, 600) > 3.5).astype(int)
    return X[:450], y[:450], X[450:] + [0, 30, 0, 0], y[450:]  # the test rows have drifted


def test_fit_and_score_learns_scaling_from_training_rows_only():
    X_tr, y_tr, X_te, y_te = fraud_data()
    result = fit_and_score(X_tr, y_tr, X_te, y_te)
    model = result["model"]
    assert isinstance(model, Pipeline)
    scaler = model[0]
    np.testing.assert_allclose(scaler.mean_, X_tr.mean(axis=0), rtol=1e-9)
    np.testing.assert_allclose(scaler.scale_, X_tr.std(axis=0), rtol=1e-9)


def test_fit_and_score_does_not_change_when_only_the_test_rows_change():
    X_tr, y_tr, X_te, y_te = fraud_data()
    a = fit_and_score(X_tr, y_tr, X_te, y_te)["model"]
    b = fit_and_score(X_tr, y_tr, X_te * 3 + 7, y_te)["model"]
    np.testing.assert_allclose(a[-1].coef_, b[-1].coef_)


def test_fit_and_score_reports_average_precision_on_each_set():
    X_tr, y_tr, X_te, y_te = fraud_data()
    result = fit_and_score(X_tr, y_tr, X_te, y_te, C=0.5)
    model = result["model"]
    assert model[-1].C == 0.5
    assert result["train_ap"] == pytest.approx(average_precision_score(y_tr, model.predict_proba(X_tr)[:, 1]))
    assert result["test_ap"] == pytest.approx(average_precision_score(y_te, model.predict_proba(X_te)[:, 1]))
