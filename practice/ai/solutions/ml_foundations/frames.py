"""pandas for machine learning - reference solution.

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
    out = tx.drop_duplicates(subset="tx_id", keep="first")
    out = out.dropna(subset=["amount_minor"])
    out = out.assign(
        amount_minor=out["amount_minor"].astype("int64"),
        category=out["category"].fillna("unknown"),
    )
    return out.reset_index(drop=True)


def merchant_summary(tx: pd.DataFrame) -> pd.DataFrame:
    """Return one row per merchant_id (the index) with columns n, total_minor and fraud_rate.

    n counts transactions, total_minor sums amount_minor and fraud_rate is the share of is_fraud rows.
    Sort by total_minor, largest first; break ties by merchant_id ascending.
    """
    summary = tx.groupby("merchant_id").agg(
        n=("tx_id", "count"),
        total_minor=("amount_minor", "sum"),
        fraud_rate=("is_fraud", "mean"),
    )
    return summary.reset_index().sort_values(["total_minor", "merchant_id"], ascending=[False, True]).set_index(
        "merchant_id"
    )


def add_country(tx: pd.DataFrame, merchants: pd.DataFrame) -> pd.DataFrame:
    """Return tx with a country column looked up from merchants (columns merchant_id, country).

    Keep every transaction, in its order, exactly once. A transaction whose merchant is unknown gets
    country "unknown". If merchants lists a merchant_id twice, raise pandas.errors.MergeError instead of
    silently duplicating transactions.
    """
    out = tx.merge(merchants[["merchant_id", "country"]], on="merchant_id", how="left", validate="many_to_one")
    return out.assign(country=out["country"].fillna("unknown"))


def flag_for_review(tx: pd.DataFrame, threshold_minor: int) -> pd.DataFrame:
    """Return a copy of tx with a boolean column needs_review.

    needs_review is True when amount_minor is at least threshold_minor or the category is "games". tx
    itself must not change - write it with one .loc / .assign step, not chained indexing.
    """
    needs = (tx["amount_minor"] >= threshold_minor) | (tx["category"] == "games")
    return tx.assign(needs_review=needs)
