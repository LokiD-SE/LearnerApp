"""Exercise - feature engineering without leakage - lesson: Feature engineering and scikit-learn pipelines.

Every rule in this file is the same rule: statistics are learnt from the TRAINING rows only, then applied
unchanged to any other rows (test rows, cross-validation folds, production requests).

``make_transactions`` is provided: it builds the synthetic SandPay card transactions used by the lesson.
"""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

CATEGORIES = ["grocery", "fuel", "travel", "electronics", "gaming"]
COUNTRIES = ["IN", "GB", "US", "DE", "SG"]
NUMERIC_COLUMNS = ["amount", "card_age_days", "hour"]
CATEGORICAL_COLUMNS = ["merchant_category", "country"]


def make_transactions(n: int = 2000, seed: int = 0) -> tuple[pd.DataFrame, pd.Series]:
    """Provided - synthetic SandPay card transactions and their fraud labels (fictional data).

    Columns: amount (float), card_age_days (float, about 8% missing), hour (0-23), merchant_category
    (str, about 3% missing) and country (str). Fraud is more likely for large amounts, electronics and
    gaming, cards younger than 30 days, the hours before 05:00 and countries other than IN.
    """
    rng = np.random.default_rng(seed)
    category = rng.choice(CATEGORIES, size=n, p=[0.35, 0.2, 0.15, 0.15, 0.15])
    country = rng.choice(COUNTRIES, size=n, p=[0.5, 0.15, 0.15, 0.1, 0.1])
    base = {"grocery": 3.2, "fuel": 3.6, "travel": 5.5, "electronics": 5.0, "gaming": 3.0}
    amount = np.round(np.exp(np.array([base[c] for c in category]) + rng.normal(0, 0.7, n)), 2)
    card_age = np.floor(rng.exponential(400, n))
    hour = rng.integers(0, 24, n)
    risk = (
        -4.2
        + 0.9 * np.log(amount / 50).clip(-2, 3)
        + np.where(np.isin(category, ["electronics", "gaming"]), 1.0, 0.0)
        + np.where(card_age < 30, 1.6, 0.0)
        + np.where(hour < 5, 0.9, 0.0)
        + np.where(country != "IN", 0.6, 0.0)
    )
    is_fraud = (rng.random(n) < 1 / (1 + np.exp(-risk))).astype(int)
    frame = pd.DataFrame(
        {
            "amount": amount,
            "card_age_days": card_age,
            "hour": hour,
            "merchant_category": category,
            "country": country,
        }
    )
    frame.loc[rng.random(n) < 0.08, "card_age_days"] = np.nan
    frame.loc[rng.random(n) < 0.03, "merchant_category"] = np.nan
    return frame, pd.Series(is_fraud, name="is_fraud")


def standardise(train: np.ndarray, test: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Scale every column to mean 0 and standard deviation 1, using statistics of ``train`` only.

    - mean and standard deviation per column, from ``train`` (population standard deviation, ddof=0 -
      what StandardScaler uses);
    - a column with standard deviation 0 is only centred (divide by 1, as StandardScaler does);
    - return new arrays (train_scaled, test_scaled); never modify the inputs.
    """
    # First draft from a notebook - the tests say something is wrong with it.
    both = np.vstack([np.asarray(train, dtype=float), np.asarray(test, dtype=float)])
    mean = both.mean(axis=0)
    std = both.std(axis=0)
    return (np.asarray(train) - mean) / std, (np.asarray(test) - mean) / std


def merchant_fraud_rate(
    train_ids: list[str],
    train_labels: list[int],
    test_ids: list[str],
    smoothing: float = 20.0,
) -> np.ndarray:
    """Encode each id in ``test_ids`` as the smoothed fraud rate of that merchant in the TRAINING rows.

    With ``prior`` = the fraud rate of all training rows, a merchant seen ``count`` times with ``frauds``
    fraudulent training rows is encoded as ``(frauds + smoothing * prior) / (count + smoothing)``. A
    merchant that never appears in training gets ``prior``. Returns a float array, one value per test id.
    """
    raise NotImplementedError("merchant_fraud_rate")


def build_preprocessor() -> ColumnTransformer:
    """A ColumnTransformer for the SandPay transaction columns, unfitted.

    - "num": NUMERIC_COLUMNS -> SimpleImputer(strategy="median", add_indicator=True) -> StandardScaler(),
      as a Pipeline with steps named "impute" and "scale";
    - "cat": CATEGORICAL_COLUMNS -> SimpleImputer(strategy="most_frequent") ->
      OneHotEncoder(handle_unknown="ignore"), as a Pipeline with steps named "impute" and "onehot";
    - any other column is dropped (the default remainder).
    """
    raise NotImplementedError("build_preprocessor")
