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


def stratified_split(y, test_fraction: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Split so each class keeps its share: for every class with n rows, exactly round(n * test_fraction)
    of them go to the test set, chosen at random. Raise ValueError unless 0 < test_fraction < 1."""
    raise NotImplementedError


def group_split(groups, test_fraction: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Split by group (for example merchant id) so no group has rows on both sides.

    Shuffle the distinct groups and put the first round(n_groups * test_fraction) of them - at least one,
    and never all of them - in the test set. Raise ValueError unless 0 < test_fraction < 1, or if there are
    fewer than two groups.
    """
    raise NotImplementedError


def fit_and_score(X_train, y_train, X_test, y_test, C: float = 1.0) -> dict:
    """Fit StandardScaler + LogisticRegression(C=C, max_iter=1000) on the training rows only and return
    {"model": the fitted Pipeline, "train_ap": ..., "test_ap": ...} - average precision of the fraud
    probabilities on each set. Nothing about the test rows may influence the fitted model."""
    # A colleague's first draft. It runs and its scores look fine - find out what is wrong with it.
    # "Scale with all the data we have, so the mean and standard deviation are more accurate."
    scaler = StandardScaler().fit(np.vstack([X_train, X_test]))
    clf = LogisticRegression(C=C, max_iter=1000).fit(scaler.transform(X_train), y_train)
    model = Pipeline([("scale", scaler), ("clf", clf)])
    return {
        "model": model,
        "train_ap": float(average_precision_score(y_train, model.predict_proba(X_train)[:, 1])),
        "test_ap": float(average_precision_score(y_test, model.predict_proba(X_test)[:, 1])),
    }
