"""pandas for machine learning - exercise. Reference solution: solutions/ml_foundations/frames.py.

Lesson: Python, NumPy and pandas for machine learning (#/lesson/python-numpy-pandas).
The SandPay transactions are synthetic. No function changes the DataFrames it is given.
"""

import pandas as pd


def clean_transactions(tx: pd.DataFrame) -> pd.DataFrame:
    """Return a cleaned copy of tx (columns tx_id, merchant_id, amount_minor, category, is_fraud).

    - keep the first row of each duplicated tx_id;
    - drop rows whose amount_minor is missing;
    - store amount_minor as int64 (amounts are whole minor units);
    - fill a missing category with "unknown";
    - number the rows 0..n-1 again.
    """
    raise NotImplementedError


def merchant_summary(tx: pd.DataFrame) -> pd.DataFrame:
    """Return one row per merchant_id (the index) with columns n, total_minor and fraud_rate.

    n counts transactions, total_minor sums amount_minor and fraud_rate is the share of is_fraud rows.
    Sort by total_minor, largest first; break ties by merchant_id ascending.
    """
    raise NotImplementedError


def add_country(tx: pd.DataFrame, merchants: pd.DataFrame) -> pd.DataFrame:
    """Return tx with a country column looked up from merchants (columns merchant_id, country).

    Keep every transaction, in its order, exactly once. A transaction whose merchant is unknown gets
    country "unknown". If merchants lists a merchant_id twice, raise pandas.errors.MergeError instead of
    silently duplicating transactions.
    """
    raise NotImplementedError


def flag_for_review(tx: pd.DataFrame, threshold_minor: int) -> pd.DataFrame:
    """Return a copy of tx with a boolean column needs_review.

    needs_review is True when amount_minor is at least threshold_minor or the category is "games". tx
    itself must not change - write it with one .loc / .assign step, not chained indexing.
    """
    # A first draft: run the tests and read the warning pandas prints.
    tx["needs_review"] = False
    tx["needs_review"][tx["amount_minor"] >= threshold_minor] = True
    return tx
