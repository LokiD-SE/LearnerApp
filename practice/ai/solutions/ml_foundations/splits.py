"""Splitting SandPay's transactions so the test score means something.

``stratified_split`` and ``group_split`` return two sorted NumPy arrays of row indices, (train, test), that
together cover every row exactly once. Use ``np.random.default_rng(seed)`` for all randomness, so the
same seed always gives the same split. ``fit_and_score`` trains the fraud model on the training rows only.
"""

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def _check_fraction(test_fraction: float) -> None:
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between 0 and 1")


def stratified_split(y, test_fraction: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Split so each class keeps its share: for every class with n rows, exactly round(n * test_fraction)
    of them go to the test set, chosen at random. Raise ValueError unless 0 < test_fraction < 1."""
    _check_fraction(test_fraction)
    y = np.asarray(y)
    rng = np.random.default_rng(seed)
    test = []
    for label in np.unique(y):
        rows = np.flatnonzero(y == label)
        n_test = round(len(rows) * test_fraction)
        test.append(rng.permutation(rows)[:n_test])
    test_idx = np.sort(np.concatenate(test))
    train_idx = np.setdiff1d(np.arange(len(y)), test_idx)
    return train_idx, test_idx


def group_split(groups, test_fraction: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Split by group (for example merchant id) so no group has rows on both sides.

    Shuffle the distinct groups and put the first round(n_groups * test_fraction) of them - at least one,
    and never all of them - in the test set. Raise ValueError unless 0 < test_fraction < 1, or if there are
    fewer than two groups.
    """
    _check_fraction(test_fraction)
    groups = np.asarray(groups)
    distinct = np.unique(groups)
    if len(distinct) < 2:
        raise ValueError("need at least two groups")
    rng = np.random.default_rng(seed)
    n_test = min(max(round(len(distinct) * test_fraction), 1), len(distinct) - 1)
    test_groups = rng.permutation(distinct)[:n_test]
    in_test = np.isin(groups, test_groups)
    return np.flatnonzero(~in_test), np.flatnonzero(in_test)


def fit_and_score(X_train, y_train, X_test, y_test, C: float = 1.0) -> dict:
    """Fit StandardScaler + LogisticRegression(C=C, max_iter=1000) on the training rows only and return
    {"model": the fitted Pipeline, "train_ap": ..., "test_ap": ...} - average precision of the fraud
    probabilities on each set. Nothing about the test rows may influence the fitted model."""
    model = Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression(C=C, max_iter=1000))])
    model.fit(X_train, y_train)
    return {
        "model": model,
        "train_ap": float(average_precision_score(y_train, model.predict_proba(X_train)[:, 1])),
        "test_ap": float(average_precision_score(y_test, model.predict_proba(X_test)[:, 1])),
    }
