"""Tests for exercises/ml_foundations/trees.py - every number is checked against scikit-learn's own trees."""

import numpy as np
import pytest
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from ml_foundations.trees import (
    best_split,
    best_threshold,
    effective_alpha,
    impurity,
    make_fraud_data,
    split_impurity,
)

pytestmark = pytest.mark.exercise

NUMERIC = ["amount", "card_age_days", "hour", "attempts_24h"]


def labels(*counts):
    return np.concatenate([np.full(c, k) for k, c in enumerate(counts)])


def fraud_sample(n=3000, seed=0):
    X, y = make_fraud_data(n, seed)
    return X[NUMERIC].to_numpy(dtype=float), y.to_numpy()


# --- impurity -----------------------------------------------------------------------------------------


def test_gini_and_entropy_of_a_node():
    y = labels(300, 100)
    assert impurity(y, "gini") == pytest.approx(0.375)
    assert impurity(y, "entropy") == pytest.approx(0.811278, abs=1e-6)
    assert impurity(labels(400, 400), "entropy") == pytest.approx(1.0)
    assert impurity(labels(5), "gini") == pytest.approx(0.0)


def test_impurity_matches_scikit_learn_root_node():
    y = np.array([0] * 70 + [1] * 20 + [2] * 10)
    X = np.arange(len(y), dtype=float).reshape(-1, 1)
    for criterion in ("gini", "entropy"):
        tree = DecisionTreeClassifier(criterion=criterion, max_depth=1, random_state=0).fit(X, y)
        assert impurity(y, criterion) == pytest.approx(tree.tree_.impurity[0])


def test_squared_error_is_the_variance_of_a_regression_node():
    y = np.array([10.0, 12.0, 20.0, 30.0])
    tree = DecisionTreeRegressor(max_depth=1).fit(np.arange(4.0).reshape(-1, 1), y)
    assert impurity(y, "squared_error") == pytest.approx(tree.tree_.impurity[0])
    assert impurity(y, "squared_error") == pytest.approx(np.var(y))


def test_impurity_edge_cases():
    assert impurity(np.array([], dtype=int), "gini") == 0.0
    assert impurity(np.array([], dtype=float), "squared_error") == 0.0
    with pytest.raises(ValueError):
        impurity(labels(3, 3), "misclassification")


# --- split_impurity -----------------------------------------------------------------------------------


def test_split_impurity_weights_children_by_size():
    # ESL 9.2.3: (400, 400) split into (300, 100) + (100, 300), or (200, 400) + (200, 0)
    a = split_impurity(labels(300, 100), labels(100, 300), "gini")
    b = split_impurity(labels(200, 400), labels(200, 0), "gini")
    assert a == pytest.approx(0.375)
    assert b == pytest.approx(1 / 3)
    assert split_impurity(labels(200, 400), labels(200, 0), "entropy") == pytest.approx(0.688722, abs=1e-6)


def test_split_impurity_small_pure_child_counts_little():
    left = labels(0, 1)  # one fraud row, pure
    right = labels(98, 1)  # almost everything else
    expected = 99 / 100 * impurity(right, "gini")
    assert split_impurity(left, right, "gini") == pytest.approx(expected)


# --- best_threshold -----------------------------------------------------------------------------------


def stump_root(model):
    t = model.tree_
    n = t.weighted_n_node_samples
    decrease = t.impurity[0] - (n[1] * t.impurity[1] + n[2] * t.impurity[2]) / n[0]
    return int(t.feature[0]), float(t.threshold[0]), float(decrease)


def test_best_threshold_on_a_tiny_example():
    x = np.array([1.0, 2.0, 3.0, 10.0, 11.0, 12.0])
    y = np.array([0, 0, 0, 1, 1, 1])
    threshold, decrease = best_threshold(x, y, "gini")
    assert threshold == pytest.approx(6.5)
    assert decrease == pytest.approx(0.5)


@pytest.mark.parametrize("criterion", ["gini", "entropy"])
def test_best_threshold_matches_a_scikit_learn_stump(criterion):
    X, y = fraud_sample()
    x = X[:, 1:2]  # card_age_days
    stump = DecisionTreeClassifier(criterion=criterion, max_depth=1, random_state=0).fit(x, y)
    _, threshold, decrease = stump_root(stump)
    got_threshold, got_decrease = best_threshold(x[:, 0], y, criterion)
    assert got_threshold == pytest.approx(threshold)
    assert got_decrease == pytest.approx(decrease)


def test_best_threshold_respects_min_samples_leaf():
    X, y = fraud_sample()
    x = X[:, 0:1]  # amount
    stump = DecisionTreeClassifier(max_depth=1, min_samples_leaf=200, random_state=0).fit(x, y)
    _, threshold, decrease = stump_root(stump)
    got_threshold, got_decrease = best_threshold(x[:, 0], y, "gini", min_samples_leaf=200)
    assert got_threshold == pytest.approx(threshold)
    assert got_decrease == pytest.approx(decrease)
    left = int((x[:, 0] <= got_threshold).sum())
    assert 200 <= left <= len(y) - 200


def test_best_threshold_without_an_allowed_split():
    assert best_threshold(np.full(10, 3.0), labels(5, 5)) == (None, 0.0)
    assert best_threshold(np.array([1.0, 2.0, 3.0]), np.array([0, 1, 0]), min_samples_leaf=2) == (None, 0.0)


def test_best_threshold_for_regression():
    rng = np.random.default_rng(1)
    x = rng.uniform(0, 1000, 400)
    y = np.where(x > 620, 25.0, 5.0) + rng.normal(0, 1, 400)
    stump = DecisionTreeRegressor(max_depth=1, random_state=0).fit(x.reshape(-1, 1), y)
    _, threshold, decrease = stump_root(stump)
    got_threshold, got_decrease = best_threshold(x, y, "squared_error")
    assert got_threshold == pytest.approx(threshold)
    assert got_decrease == pytest.approx(decrease)


# --- best_split ---------------------------------------------------------------------------------------


def test_best_split_matches_the_root_of_a_scikit_learn_tree():
    X, y = fraud_sample()
    stump = DecisionTreeClassifier(max_depth=1, random_state=0).fit(X, y)
    feature, threshold, decrease = stump_root(stump)
    got = best_split(X, y, "gini")
    assert got[0] == feature
    assert got[1] == pytest.approx(threshold)
    assert got[2] == pytest.approx(decrease)


def test_best_split_ignores_a_useless_column_and_breaks_ties_by_index():
    x = np.array([1.0, 2.0, 3.0, 10.0, 11.0, 12.0])
    y = np.array([0, 0, 0, 1, 1, 1])
    X = np.column_stack([np.zeros(6), x, x])  # constant, then two identical informative columns
    feature, threshold, decrease = best_split(X, y)
    assert (feature, threshold) == (1, pytest.approx(6.5))
    assert decrease == pytest.approx(0.5)
    assert best_split(np.zeros((6, 2)), y) == (None, None, 0.0)


# --- effective_alpha ----------------------------------------------------------------------------------


def test_effective_alpha_by_hand():
    # node: 100 of 1000 rows, gini 0.5; branch leaves: 60 rows at 0.2 and 40 rows at 0.1
    alpha = effective_alpha(0.5, 100, [0.2, 0.1], [60, 40], 1000)
    assert alpha == pytest.approx((0.05 - (0.012 + 0.004)) / 1)
    with pytest.raises(ValueError):
        effective_alpha(0.5, 100, [0.2], [100], 1000)


def leaves_below(tree, node):
    if tree.children_left[node] == -1:
        return [node]
    return leaves_below(tree, tree.children_left[node]) + leaves_below(tree, tree.children_right[node])


def test_weakest_link_matches_the_scikit_learn_pruning_path():
    X, y = fraud_sample()
    model = DecisionTreeClassifier(max_leaf_nodes=6, random_state=0).fit(X, y)
    t = model.tree_
    n_total = int(t.n_node_samples[0])
    alphas = []
    for node in range(t.node_count):
        if t.children_left[node] == -1:
            continue
        leaves = leaves_below(t, node)
        alphas.append(
            effective_alpha(
                float(t.impurity[node]),
                int(t.n_node_samples[node]),
                [float(t.impurity[i]) for i in leaves],
                [int(t.n_node_samples[i]) for i in leaves],
                n_total,
            )
        )
    path = model.cost_complexity_pruning_path(X, y)
    assert min(alphas) == pytest.approx(path.ccp_alphas[1])
