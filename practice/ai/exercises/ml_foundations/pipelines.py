"""Exercise - pipelines, honest cross-validation, tuning and saving a model - lesson: scikit-learn-pipelines.

Solve ``features.py`` first: ``make_fraud_pipeline`` uses its ``build_preprocessor``.
"""

import json
import platform
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.feature_selection import SelectKBest
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline, make_pipeline

from ml_foundations.features import build_preprocessor

DEFAULT_GRID = {
    "model__C": [0.01, 0.1, 1, 10],
    "preprocess__num__impute__strategy": ["mean", "median"],
}


def select_and_score(X: np.ndarray, y: np.ndarray, k: int = 20, seed: int = 0) -> float:
    """Mean 5-fold cross-validated accuracy of "keep the k best features, then logistic regression".

    Use StratifiedKFold(n_splits=5, shuffle=True, random_state=seed) and
    LogisticRegression(max_iter=1000). The estimate must be honest: on labels that are pure noise it must
    come out near 0.5, however many noise columns there are.
    """
    # First draft - fast and the score looks great. Is it honest?
    X_selected = SelectKBest(k=k).fit_transform(X, y)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    return float(cross_val_score(LogisticRegression(max_iter=1000), X_selected, y, cv=cv).mean())


def make_fraud_pipeline(C: float = 1.0) -> Pipeline:
    """An unfitted Pipeline: ("preprocess", build_preprocessor()) then
    ("model", LogisticRegression(C=C, max_iter=1000))."""
    raise NotImplementedError("make_fraud_pipeline")


def tune_fraud_pipeline(
    X: pd.DataFrame, y: pd.Series, param_grid: dict | None = None, seed: int = 0
) -> GridSearchCV:
    """Grid-search the fraud pipeline and return the FITTED GridSearchCV.

    - estimator: make_fraud_pipeline() - preprocessing inside the search, so each fold fits its own;
    - param_grid: ``param_grid`` or DEFAULT_GRID;
    - scoring="roc_auc"; cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=seed).
    """
    # First draft - prepare the data once, then tune the model on it.
    X_ready = build_preprocessor().fit_transform(X)
    search = GridSearchCV(
        LogisticRegression(max_iter=1000),
        {"C": [0.01, 0.1, 1, 10]},
        scoring="roc_auc",
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=seed),
    )
    return search.fit(X_ready, y)


def nested_cv_scores(
    X: pd.DataFrame, y: pd.Series, param_grid: dict | None = None, seed: int = 0
) -> np.ndarray:
    """Nested cross-validation: the ROC AUC of the WHOLE tuning procedure on 5 outer folds.

    - inner loop: the same unfitted GridSearchCV as tune_fraud_pipeline builds (inner cv random_state=seed);
    - outer loop: cross_val_score with StratifiedKFold(n_splits=5, shuffle=True, random_state=seed + 1)
      and scoring="roc_auc";
    - return the 5 outer scores as a NumPy array.
    """
    raise NotImplementedError("nested_cv_scores")


def save_model(model: Pipeline, path: str | Path) -> Path:
    """Save a fitted model with joblib to ``path`` and write its metadata next to it.

    The metadata file is ``path`` with the suffix ".json": {"sklearn_version": sklearn.__version__,
    "python_version": platform.python_version(), "features": the input column names the model was fitted
    on (model.feature_names_in_, as a list)}. Return the metadata file's path.
    """
    # First draft - saves the model, nothing else.
    path = Path(path)
    joblib.dump(model, path)
    return path.with_suffix(".json")


def load_model(path: str | Path) -> Pipeline:
    """Load a model saved by save_model - but only into the scikit-learn version it was saved with.

    Read the metadata first. If its "sklearn_version" differs from sklearn.__version__, raise ValueError
    naming both versions WITHOUT opening the model file (loading runs pickle; an unsupported version can
    give wrong results). Otherwise return joblib.load(path). Only load files from a source you trust.
    """
    # First draft.
    return joblib.load(path)
