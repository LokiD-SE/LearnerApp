"""Exercise: feature engineering without leakage (lesson: scikit-learn-pipelines).

Run: .venv/bin/python -m pytest tests/ml_foundations/test_features.py
"""

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from ml_foundations.features import (
    CATEGORICAL_COLUMNS,
    NUMERIC_COLUMNS,
    build_preprocessor,
    make_transactions,
    merchant_fraud_rate,
    standardise,
)

pytestmark = pytest.mark.exercise


@pytest.fixture(scope="module")
def split():
    X, y = make_transactions(n=1200, seed=4)
    return train_test_split(X, y, test_size=0.25, stratify=y, random_state=0)


# --- standardise -----------------------------------------------------------------------------------------


def test_standardise_matches_standard_scaler_fitted_on_train_only():
    rng = np.random.default_rng(1)
    train = rng.normal([50.0, 3.0], [20.0, 1.0], size=(80, 2))
    test = rng.normal([500.0, 3.0], [20.0, 1.0], size=(20, 2))  # the test rows come from somewhere else
    scaler = StandardScaler().fit(train)
    train_scaled, test_scaled = standardise(train, test)
    assert_allclose(train_scaled, scaler.transform(train))
    assert_allclose(test_scaled, scaler.transform(test))


def test_standardise_scaled_train_has_mean_0_and_std_1_whatever_the_test_rows_are():
    train = np.array([[1.0, 10.0], [2.0, 20.0], [3.0, 30.0], [4.0, 40.0]])
    for test in (np.array([[1000.0, -5.0]]), np.array([[0.0, 0.0], [9.0, 9.0]])):
        train_scaled, _ = standardise(train, test)
        assert_allclose(train_scaled.mean(axis=0), [0.0, 0.0], atol=1e-12)
        assert_allclose(train_scaled.std(axis=0), [1.0, 1.0])


def test_standardise_only_centres_a_constant_column():
    train = np.array([[5.0, 1.0], [5.0, 2.0], [5.0, 3.0]])
    test = np.array([[7.0, 2.0]])
    train_scaled, test_scaled = standardise(train, test)
    assert np.isfinite(train_scaled).all() and np.isfinite(test_scaled).all()
    assert_allclose(train_scaled[:, 0], [0.0, 0.0, 0.0])
    assert test_scaled[0, 0] == pytest.approx(2.0)


def test_standardise_does_not_modify_its_inputs():
    train = np.array([[1.0], [2.0], [3.0]])
    test = np.array([[4.0]])
    standardise(train, test)
    assert_allclose(train, [[1.0], [2.0], [3.0]])
    assert_allclose(test, [[4.0]])


# --- merchant_fraud_rate ---------------------------------------------------------------------------------


def test_merchant_fraud_rate_uses_smoothed_training_rates():
    train_ids = ["m1"] * 10 + ["m2"] * 30
    train_labels = [1] * 5 + [0] * 5 + [1] * 3 + [0] * 27  # m1: 5 of 10, m2: 3 of 30, prior 8/40 = 0.2
    encoded = merchant_fraud_rate(train_ids, train_labels, ["m1", "m2"], smoothing=10.0)
    assert encoded == pytest.approx([(5 + 10 * 0.2) / 20, (3 + 10 * 0.2) / 40])


def test_merchant_fraud_rate_gives_an_unseen_merchant_the_prior():
    encoded = merchant_fraud_rate(["a", "a", "b", "b"], [1, 0, 0, 0], ["zzz", "a"], smoothing=2.0)
    assert encoded[0] == pytest.approx(0.25)
    assert encoded[1] == pytest.approx((1 + 2 * 0.25) / (2 + 2))
    assert isinstance(encoded, np.ndarray) and encoded.dtype == float


def test_merchant_fraud_rate_with_zero_smoothing_is_the_raw_training_rate():
    encoded = merchant_fraud_rate(["a", "a", "a", "b"], [1, 1, 0, 0], ["a", "b", "a"], smoothing=0.0)
    assert encoded == pytest.approx([2 / 3, 0.0, 2 / 3])


# --- build_preprocessor ----------------------------------------------------------------------------------


def test_build_preprocessor_returns_an_unfitted_column_transformer_with_the_named_steps():
    pre = build_preprocessor()
    assert isinstance(pre, ColumnTransformer)
    assert not hasattr(pre, "transformers_"), "return it unfitted - fitting is the caller's job"
    by_name = {name: (step, cols) for name, step, cols in pre.transformers}
    assert set(by_name) == {"num", "cat"}
    assert list(by_name["num"][1]) == NUMERIC_COLUMNS
    assert list(by_name["cat"][1]) == CATEGORICAL_COLUMNS
    assert [n for n, _ in by_name["num"][0].steps] == ["impute", "scale"]
    assert [n for n, _ in by_name["cat"][0].steps] == ["impute", "onehot"]


def test_build_preprocessor_handles_missing_values_and_names_its_features(split):
    X_train, X_test, _, _ = split
    pre = build_preprocessor().fit(X_train)
    out = pre.transform(X_test)
    out = out.toarray() if hasattr(out, "toarray") else np.asarray(out)
    assert not np.isnan(out).any()
    names = list(pre.get_feature_names_out())
    assert names[:4] == ["num__amount", "num__card_age_days", "num__hour", "num__missingindicator_card_age_days"]
    assert "cat__merchant_category_gaming" in names and "cat__country_IN" in names
    assert out.shape == (len(X_test), len(names))


def test_build_preprocessor_learns_its_statistics_from_the_training_rows(split):
    X_train, _, _, _ = split
    pre = build_preprocessor().fit(X_train)
    impute = pre.named_transformers_["num"].named_steps["impute"]
    assert impute.statistics_ == pytest.approx(X_train[NUMERIC_COLUMNS].median().to_numpy())
    scaled = pre.transform(X_train)
    scaled = scaled.toarray() if hasattr(scaled, "toarray") else np.asarray(scaled)
    assert scaled[:, :3].mean(axis=0) == pytest.approx([0, 0, 0], abs=1e-9)


def test_build_preprocessor_accepts_a_country_it_never_saw(split):
    X_train, _, _, _ = split
    pre = build_preprocessor().fit(X_train)
    new = pd.DataFrame(
        {
            "amount": [120.0],
            "card_age_days": [np.nan],
            "hour": [2],
            "merchant_category": ["travel"],
            "country": ["FR"],
        }
    )
    row = pre.transform(new)
    row = row.toarray() if hasattr(row, "toarray") else np.asarray(row)
    names = list(pre.get_feature_names_out())
    country = [i for i, n in enumerate(names) if n.startswith("cat__country_")]
    assert row[0, country].sum() == 0, "an unknown category becomes all zeros"
    # The indicator is 1 for a missing value - then scaled with the other numeric columns, so it is positive.
    assert row[0, names.index("num__missingindicator_card_age_days")] > 0
    assert row[0, names.index("cat__merchant_category_travel")] == 1
