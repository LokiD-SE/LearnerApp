"""Tests for exercises/ml_foundations/ensembles.py - bagging, out-of-bag rows, boosting, importances, early stopping."""

import math

import numpy as np
import pytest
from sklearn.ensemble import GradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.tree import DecisionTreeClassifier

from ml_foundations.ensembles import (
    bootstrap_indices,
    early_stopping_iteration,
    fit_boosting,
    fit_forest,
    forest_proba,
    out_of_bag_indices,
    out_of_bag_probability,
    out_of_bag_proba,
    permutation_importance,
    predict_boosting,
    tree_proba,
)

pytestmark = pytest.mark.exercise


def fraud_like(n=600, seed=0):
    """Two informative columns (a threshold and an interaction) and one noise column."""
    rng = np.random.default_rng(seed)
    amount = rng.uniform(0, 1000, n)
    card_age = rng.uniform(0, 400, n)
    noise = rng.normal(size=n)
    logit = -3 + 3 * (amount > 600) + 2.5 * ((card_age < 60) & (amount > 300))
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return np.column_stack([amount, card_age, noise]), y


# --- bootstrap and out-of-bag -------------------------------------------------------------------------


def test_out_of_bag_probability():
    assert out_of_bag_probability(1) == 0.0
    assert out_of_bag_probability(2) == pytest.approx(0.25)
    assert out_of_bag_probability(10) == pytest.approx(0.348678, abs=1e-6)
    assert out_of_bag_probability(15000) == pytest.approx(math.exp(-1), abs=1e-4)
    with pytest.raises(ValueError):
        out_of_bag_probability(0)


def test_bootstrap_indices_replays_the_generator():
    got = bootstrap_indices(8, np.random.default_rng(3))
    expected = np.random.default_rng(3).integers(0, 8, size=8)
    np.testing.assert_array_equal(got, expected)


def test_out_of_bag_indices():
    np.testing.assert_array_equal(out_of_bag_indices(6, np.array([0, 0, 2, 5, 5, 2])), [1, 3, 4])
    np.testing.assert_array_equal(out_of_bag_indices(3, np.array([0, 1, 2])), np.array([], dtype=int))


def test_about_a_third_of_rows_are_out_of_bag():
    rng = np.random.default_rng(0)
    shares = [len(out_of_bag_indices(5000, bootstrap_indices(5000, rng))) / 5000 for _ in range(20)]
    assert np.mean(shares) == pytest.approx(math.exp(-1), abs=0.01)


# --- the forest ---------------------------------------------------------------------------------------


def test_fit_forest_replays_samples_and_seeds():
    X, y = fraud_like()
    forest = fit_forest(X, y, n_trees=4, max_features=None, seed=7)
    rng = np.random.default_rng(7)
    assert len(forest) == 4
    for tree, sample in forest:
        expected = rng.integers(0, len(y), size=len(y))
        state = int(rng.integers(0, 2**31 - 1))
        np.testing.assert_array_equal(sample, expected)
        assert isinstance(tree, DecisionTreeClassifier)
        assert tree.random_state == state
        assert tree.max_features is None
        twin = DecisionTreeClassifier(random_state=state).fit(X[sample], y[sample])
        np.testing.assert_allclose(tree_proba(tree, X), tree_proba(twin, X))


def test_forest_proba_averages_probabilities():
    X, y = fraud_like()
    forest = [
        (DecisionTreeClassifier(max_depth=2, random_state=0).fit(X[s], y[s]), s)
        for s in (np.arange(0, 300), np.arange(300, 600))
    ]
    expected = (tree_proba(forest[0][0], X) + tree_proba(forest[1][0], X)) / 2
    got = forest_proba(forest, X)
    np.testing.assert_allclose(got, expected)
    assert len(np.unique(np.round(got, 6))) > 2  # probabilities, not 0/1 votes


def test_out_of_bag_proba_uses_only_trees_that_did_not_see_the_row():
    X, y = fraud_like()
    forest = fit_forest(X, y, n_trees=25, seed=1)
    oob = out_of_bag_proba(forest, X)
    assert oob.shape == (len(y),)
    for i in (0, 17, 333):
        trees = [tree for tree, sample in forest if i not in set(sample.tolist())]
        expected = np.mean([tree_proba(tree, X[i : i + 1])[0] for tree in trees])
        assert oob[i] == pytest.approx(expected)
    # a fully grown tree predicts its own training rows perfectly, so in-bag scores would look perfect
    ok = ~np.isnan(oob)
    assert roc_auc_score(y, forest_proba(forest, X)) > 0.99
    assert roc_auc_score(y[ok], oob[ok]) < 0.95


def test_out_of_bag_proba_is_nan_for_rows_in_every_sample():
    X, y = fraud_like(n=40)
    forest = fit_forest(X, y, n_trees=1, seed=0)
    oob = out_of_bag_proba(forest, X)
    in_bag = np.isin(np.arange(40), forest[0][1])
    assert np.isnan(oob[in_bag]).all()
    assert not np.isnan(oob[~in_bag]).any()


# --- boosting -----------------------------------------------------------------------------------------


def regression_data(seed=2):
    rng = np.random.default_rng(seed)
    X = rng.uniform(0, 1000, (500, 3))
    y = 0.3 + 0.02 * X[:, 0] + np.where(X[:, 1] > 500, 5.0, 0.0) + rng.normal(0, 1, 500)
    return X, y


def test_boosting_matches_gradient_boosting_regressor():
    X, y = regression_data()
    init, trees = fit_boosting(X, y, n_trees=50, learning_rate=0.1, max_depth=3)
    assert init == pytest.approx(y.mean())
    assert len(trees) == 50
    reference = GradientBoostingRegressor(n_estimators=50, learning_rate=0.1, max_depth=3, random_state=0).fit(X, y)
    np.testing.assert_allclose(predict_boosting(init, trees, X, 0.1), reference.predict(X), atol=1e-8)


def test_each_tree_fits_the_current_residuals():
    X, y = regression_data()
    init, trees = fit_boosting(X, y, n_trees=3, learning_rate=0.5, max_depth=2)
    F = np.full(len(y), init)
    for tree in trees:
        # the leaves of a squared-error tree hold the mean of what it was fitted to - here the residuals
        leaf = tree.apply(X)
        residual = y - F
        for node in np.unique(leaf):
            assert tree.tree_.value[node].ravel()[0] == pytest.approx(residual[leaf == node].mean())
        F = F + 0.5 * tree.predict(X)


def test_training_error_falls_as_trees_are_added():
    X, y = regression_data()
    errors = []
    for n in (1, 5, 25, 100):
        init, trees = fit_boosting(X, y, n_trees=n, learning_rate=0.1, max_depth=2)
        errors.append(np.mean((y - predict_boosting(init, trees, X, 0.1)) ** 2))
    assert errors == sorted(errors, reverse=True)


# --- permutation importance ---------------------------------------------------------------------------


def test_permutation_importance_replays_the_shuffles():
    X, y = fraud_like()
    weights = np.array([0.003, -0.002, 0.5])

    def score(data, labels):
        return float(np.mean((data @ weights > 1.0) == labels))

    before = X.copy()
    got = permutation_importance(score, X, y, n_repeats=3, seed=5)
    np.testing.assert_array_equal(X, before)
    assert got.shape == (3, 3)
    rng = np.random.default_rng(5)
    baseline = score(X, y)
    for j in range(3):
        for r in range(3):
            shuffled = X.copy()
            shuffled[:, j] = X[rng.permutation(len(y)), j]
            assert got[j, r] == pytest.approx(baseline - score(shuffled, y))


def test_permutation_importance_ranks_real_signal_above_noise():
    X, y = fraud_like(n=2000, seed=3)
    X_test, y_test = fraud_like(n=2000, seed=4)
    forest = fit_forest(X, y, n_trees=30, seed=0)

    def auc(data, labels):
        return roc_auc_score(labels, forest_proba(forest, data))

    mean = permutation_importance(auc, X_test, y_test, n_repeats=3, seed=0).mean(axis=1)
    assert mean[0] > mean[1] > abs(mean[2])
    assert abs(mean[2]) < 0.02


# --- early stopping -----------------------------------------------------------------------------------


def test_early_stopping_by_hand():
    rising = [float(i) for i in range(30)]
    assert early_stopping_iteration(rising, n_iter_no_change=5) == 29
    flat_after_3 = [0.0, 1.0, 2.0, 3.0] + [3.0] * 20
    assert early_stopping_iteration(flat_after_3, n_iter_no_change=5) == 8
    tiny_gains = [0.0] + [1e-9 * i for i in range(1, 20)]
    assert early_stopping_iteration(tiny_gains, n_iter_no_change=3, tol=1e-7) == 3


@pytest.mark.parametrize("learning_rate", [1.0, 0.3, 0.1])
def test_early_stopping_predicts_hist_gradient_boosting_n_iter(learning_rate):
    X, y = fraud_like(n=4000, seed=9)
    model = HistGradientBoostingClassifier(
        learning_rate=learning_rate, max_iter=500, early_stopping=True, random_state=0
    ).fit(X, y)
    scores = list(model.validation_score_)
    assert early_stopping_iteration(scores, n_iter_no_change=10, tol=1e-7) == model.n_iter_
