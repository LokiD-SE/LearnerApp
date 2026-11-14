"""Exercise: pipelines, honest cross-validation, tuning and saving (lesson: scikit-learn-pipelines).

Solve features.py first - the pipeline uses its build_preprocessor.
Run: .venv/bin/python -m pytest tests/ml_foundations/test_pipelines.py
"""

import json

import numpy as np
import pandas as pd
import pytest
import sklearn
from numpy.testing import assert_allclose
from sklearn.compose import ColumnTransformer
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

from ml_foundations.features import make_transactions
from ml_foundations.pipelines import (
    load_model,
    make_fraud_pipeline,
    nested_cv_scores,
    save_model,
    select_and_score,
    tune_fraud_pipeline,
)

pytestmark = pytest.mark.exercise

SMALL_GRID = {"model__C": [0.1, 1.0], "preprocess__num__impute__strategy": ["mean", "median"]}


@pytest.fixture(scope="module")
def data():
    return make_transactions(n=800, seed=5)


# --- select_and_score --------------------------------------------------------------------------------------


def test_select_and_score_is_near_chance_when_the_labels_are_noise():
    rng = np.random.default_rng(7)
    X = rng.standard_normal((200, 3000))
    y = rng.integers(0, 2, 200)
    score = select_and_score(X, y, k=20, seed=0)
    assert isinstance(score, float)
    assert 0.35 <= score <= 0.65, (
        f"accuracy {score:.3f} on pure noise - the feature selection saw the rows it is scored on"
    )


def test_select_and_score_still_finds_real_signal():
    X, y = make_classification(
        n_samples=300, n_features=200, n_informative=5, n_redundant=0, random_state=3
    )
    assert select_and_score(X, y, k=10, seed=0) > 0.75


# --- make_fraud_pipeline -----------------------------------------------------------------------------------


def test_make_fraud_pipeline_chains_the_preprocessor_and_the_model():
    pipe = make_fraud_pipeline(C=0.5)
    assert isinstance(pipe, Pipeline)
    assert [name for name, _ in pipe.steps] == ["preprocess", "model"]
    assert isinstance(pipe.named_steps["preprocess"], ColumnTransformer)
    model = pipe.named_steps["model"]
    assert isinstance(model, LogisticRegression)
    assert model.C == 0.5 and model.max_iter == 1000


def test_make_fraud_pipeline_fits_raw_rows_and_scores_new_ones(data):
    X, y = data
    pipe = make_fraud_pipeline().fit(X.iloc[:600], y.iloc[:600])
    new = X.iloc[600:].copy()
    new.loc[new.index[0], "country"] = "FR"  # never seen in training
    proba = pipe.predict_proba(new)
    assert proba.shape == (200, 2)
    assert_allclose(proba.sum(axis=1), 1.0)


# --- tune_fraud_pipeline -----------------------------------------------------------------------------------


def test_tune_fraud_pipeline_searches_the_whole_pipeline(data):
    X, y = data
    search = tune_fraud_pipeline(X, y, param_grid=SMALL_GRID, seed=0)
    assert isinstance(search, GridSearchCV)
    assert isinstance(search.estimator, Pipeline), "tune the pipeline, so every fold fits its own preprocessing"
    assert search.scoring == "roc_auc"
    assert len(search.cv_results_["params"]) == 4
    assert set(search.best_params_) == set(SMALL_GRID)
    # The refitted best pipeline takes raw rows - preprocessing travels with the model.
    assert search.predict_proba(X.head(3)).shape == (3, 2)


def test_tune_fraud_pipeline_uses_shuffled_stratified_folds_with_the_seed(data):
    X, y = data
    search = tune_fraud_pipeline(X, y, param_grid={"model__C": [1.0]}, seed=3)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=3)
    expected = cross_val_score(make_fraud_pipeline(C=1.0), X, y, cv=cv, scoring="roc_auc").mean()
    assert search.best_score_ == pytest.approx(expected)


def test_tune_fraud_pipeline_defaults_to_the_lesson_grid():
    X, y = make_transactions(n=300, seed=6)
    search = tune_fraud_pipeline(X, y)
    assert len(search.cv_results_["params"]) == 8


# --- nested_cv_scores --------------------------------------------------------------------------------------


def test_nested_cv_scores_scores_the_tuning_procedure_on_outer_folds():
    X, y = make_transactions(n=300, seed=8)
    grid = {"model__C": [0.1]}
    scores = nested_cv_scores(X, y, param_grid=grid, seed=0)
    assert isinstance(scores, np.ndarray) and scores.shape == (5,)
    inner = GridSearchCV(
        make_fraud_pipeline(),
        grid,
        scoring="roc_auc",
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=0),
    )
    outer = StratifiedKFold(n_splits=5, shuffle=True, random_state=1)
    assert_allclose(scores, cross_val_score(inner, X, y, cv=outer, scoring="roc_auc"))


# --- save_model and load_model -----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fitted(data):
    X, y = data
    return make_fraud_pipeline().fit(X, y)


def test_save_model_round_trips_and_writes_metadata(tmp_path, data, fitted):
    X, _ = data
    meta_path = save_model(fitted, tmp_path / "fraud.joblib")
    assert meta_path == tmp_path / "fraud.json"
    meta = json.loads(meta_path.read_text())
    assert meta["sklearn_version"] == sklearn.__version__
    assert meta["python_version"].count(".") == 2
    assert meta["features"] == list(X.columns)
    loaded = load_model(tmp_path / "fraud.joblib")
    assert_allclose(loaded.predict_proba(X.head(20)), fitted.predict_proba(X.head(20)))


def test_load_model_refuses_another_scikit_learn_version(tmp_path, fitted):
    save_model(fitted, tmp_path / "fraud.joblib")
    meta_path = tmp_path / "fraud.json"
    meta = json.loads(meta_path.read_text())
    meta["sklearn_version"] = "1.4.2"
    meta_path.write_text(json.dumps(meta))
    with pytest.raises(ValueError) as error:
        load_model(tmp_path / "fraud.joblib")
    assert "1.4.2" in str(error.value) and sklearn.__version__ in str(error.value)


def test_load_model_checks_the_version_before_opening_the_model_file(tmp_path, fitted):
    save_model(fitted, tmp_path / "fraud.joblib")
    meta_path = tmp_path / "fraud.json"
    meta = json.loads(meta_path.read_text())
    meta["sklearn_version"] = "0.0.1"
    meta_path.write_text(json.dumps(meta))
    (tmp_path / "fraud.joblib").write_bytes(b"not a pickle - opening this would fail differently")
    with pytest.raises(ValueError, match="0.0.1"):
        load_model(tmp_path / "fraud.joblib")


def test_save_model_records_columns_of_a_dataframe_only(tmp_path):
    frame = pd.DataFrame({"a": [0.0, 1.0, 2.0, 3.0], "b": [1.0, 0.0, 1.0, 0.0]})
    model = LogisticRegression().fit(frame, [0, 1, 0, 1])
    save_model(model, tmp_path / "tiny.joblib")
    assert json.loads((tmp_path / "tiny.json").read_text())["features"] == ["a", "b"]
