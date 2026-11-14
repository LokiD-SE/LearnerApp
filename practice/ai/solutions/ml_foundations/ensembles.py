"""Exercise - bagging, boosting and honest importances - lesson: Decision trees, random forests and boosting.

You build the moving parts of tree ensembles yourself, on top of scikit-learn's single trees:

- bootstrap samples and their out-of-bag rows, and a small random forest with out-of-bag predictions;
- gradient boosting for squared error - each tree fits the residuals, scaled by the learning rate;
- permutation importance - how much a score drops when one column is shuffled;
- the early-stopping rule HistGradientBoosting uses, so you can predict its ``n_iter_``.

Every function that draws random numbers takes a seed and uses ``np.random.default_rng(seed)`` exactly as
its docstring says, so results are reproducible and the tests can replay them.
"""

from collections.abc import Callable

import numpy as np
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor


def out_of_bag_probability(n: int) -> float:
    """Probability that one given row is NOT drawn in a bootstrap sample of size ``n`` from ``n`` rows.

    Each of the n draws misses the row with probability 1 - 1/n, so the answer is (1 - 1/n) ** n, which
    tends to 1/e (about 0.368) as n grows.
    """
    if n < 1:
        raise ValueError("n must be at least 1")
    return (1 - 1 / n) ** n


def bootstrap_indices(n: int, rng: np.random.Generator) -> np.ndarray:
    """A bootstrap sample: ``n`` row indices drawn with replacement, as ``rng.integers(0, n, size=n)``."""
    return rng.integers(0, n, size=n)


def out_of_bag_indices(n: int, sample: np.ndarray) -> np.ndarray:
    """The sorted indices in ``range(n)`` that do not appear in ``sample``."""
    in_bag = np.zeros(n, dtype=bool)
    in_bag[np.asarray(sample)] = True
    return np.flatnonzero(~in_bag)


def fit_forest(
    X: np.ndarray, y: np.ndarray, n_trees: int = 50, max_features: str | int | float | None = "sqrt", seed: int = 0
) -> list[tuple[DecisionTreeClassifier, np.ndarray]]:
    """A small random forest for binary labels: a list of (fitted tree, its bootstrap sample).

    With ``rng = np.random.default_rng(seed)``, for each tree in turn: draw ``sample = bootstrap_indices(n,
    rng)``, then fit ``DecisionTreeClassifier(max_features=max_features, random_state=int(rng.integers(0,
    2**31 - 1)))`` on ``X[sample], y[sample]``. ``max_features`` is the random subset of columns each split
    may consider - the "random" in random forest; ``None`` means every column (plain bagging).
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y)
    rng = np.random.default_rng(seed)
    forest = []
    for _ in range(n_trees):
        sample = bootstrap_indices(len(y), rng)
        tree = DecisionTreeClassifier(max_features=max_features, random_state=int(rng.integers(0, 2**31 - 1)))
        tree.fit(X[sample], y[sample])
        forest.append((tree, sample))
    return forest


def tree_proba(tree: DecisionTreeClassifier, X: np.ndarray) -> np.ndarray:
    """P(class 1) from one tree - 0.0 if the tree never saw class 1 in its sample (provided)."""
    proba = tree.predict_proba(np.asarray(X, dtype=float))
    classes = list(tree.classes_)
    return proba[:, classes.index(1)] if 1 in classes else np.zeros(len(proba))


def forest_proba(forest: list[tuple[DecisionTreeClassifier, np.ndarray]], X: np.ndarray) -> np.ndarray:
    """P(class 1) from the forest: the mean of ``tree_proba`` over its trees (scikit-learn averages
    probabilities rather than counting votes)."""
    return np.mean([tree_proba(tree, X) for tree, _ in forest], axis=0)


def out_of_bag_proba(forest: list[tuple[DecisionTreeClassifier, np.ndarray]], X: np.ndarray) -> np.ndarray:
    """Out-of-bag P(class 1) for each TRAINING row of ``X`` (the rows the forest was fitted on).

    For row i, average ``tree_proba`` over only the trees whose bootstrap sample did not contain i. A row
    that was in every sample has no out-of-bag prediction: return ``np.nan`` for it, never 0.
    """
    X = np.asarray(X, dtype=float)
    total = np.zeros(len(X))
    count = np.zeros(len(X))
    for tree, sample in forest:
        oob = out_of_bag_indices(len(X), sample)
        if len(oob):
            total[oob] += tree_proba(tree, X[oob])
            count[oob] += 1
    with np.errstate(invalid="ignore"):
        return np.where(count > 0, total / np.where(count > 0, count, 1), np.nan)


def fit_boosting(
    X: np.ndarray, y: np.ndarray, n_trees: int = 100, learning_rate: float = 0.1, max_depth: int = 3
) -> tuple[float, list[DecisionTreeRegressor]]:
    """Gradient boosting for squared error. Return ``(init, trees)``.

    Start from ``init = mean(y)`` and ``F = init`` for every row. Then, ``n_trees`` times: the negative
    gradient of squared error is the residual ``y - F``; fit ``DecisionTreeRegressor(max_depth=max_depth,
    random_state=0)`` to it and add ``learning_rate * tree.predict(X)`` to ``F``. This reproduces
    scikit-learn's ``GradientBoostingRegressor`` with the same three settings.
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    init = float(y.mean())
    F = np.full(len(y), init)
    trees = []
    for _ in range(n_trees):
        tree = DecisionTreeRegressor(max_depth=max_depth, random_state=0).fit(X, y - F)
        F += learning_rate * tree.predict(X)
        trees.append(tree)
    return init, trees


def predict_boosting(
    init: float, trees: list[DecisionTreeRegressor], X: np.ndarray, learning_rate: float = 0.1
) -> np.ndarray:
    """Predictions of a boosted model: ``init + learning_rate * sum(tree.predict(X))``."""
    X = np.asarray(X, dtype=float)
    out = np.full(len(X), init, dtype=float)
    for tree in trees:
        out += learning_rate * tree.predict(X)
    return out


def permutation_importance(
    score: Callable[[np.ndarray, np.ndarray], float],
    X: np.ndarray,
    y: np.ndarray,
    n_repeats: int = 5,
    seed: int = 0,
) -> np.ndarray:
    """Permutation importance of every column: an array of shape (n_features, n_repeats).

    ``score(X, y)`` returns a higher-is-better score of an already fitted model. Compute the baseline
    ``score(X, y)`` once. Then, with ``rng = np.random.default_rng(seed)``, for each column j (outer loop)
    and each repeat r (inner loop): copy X, replace column j by ``X[rng.permutation(n), j]``, and store
    ``baseline - score(shuffled, y)``. Never modify ``X``.
    """
    X = np.asarray(X)
    baseline = score(X, y)
    rng = np.random.default_rng(seed)
    n, p = X.shape
    importances = np.empty((p, n_repeats))
    for j in range(p):
        for r in range(n_repeats):
            shuffled = X.copy()
            shuffled[:, j] = X[rng.permutation(n), j]
            importances[j, r] = baseline - score(shuffled, y)
    return importances


def early_stopping_iteration(scores: list[float], n_iter_no_change: int = 10, tol: float = 1e-7) -> int:
    """The number of iterations HistGradientBoosting fits before early stopping, given its scores.

    ``scores[0]`` is the validation score before the first iteration and ``scores[i]`` the score after
    iteration i (higher is better, like ``validation_score_``). After each iteration i, scikit-learn stops if
    none of the last ``n_iter_no_change`` scores beats the score ``n_iter_no_change`` iterations before
    them by more than ``tol``: stop at the first i >= n_iter_no_change with
    ``max(scores[i - n_iter_no_change + 1 : i + 1]) <= scores[i - n_iter_no_change] + tol``.
    Return that i, or ``len(scores) - 1`` if it never stops.
    """
    for i in range(n_iter_no_change, len(scores)):
        reference = scores[i - n_iter_no_change] + tol
        recent = scores[i - n_iter_no_change + 1 : i + 1]
        if not any(score > reference for score in recent):
            return i
    return len(scores) - 1
