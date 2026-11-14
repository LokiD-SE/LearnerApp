"""Checks exercises/ml_foundations/frames.py - lesson python-numpy-pandas. The data is synthetic."""

import numpy as np
import pandas as pd
import pytest
from ml_foundations.frames import add_country, clean_transactions, flag_for_review, merchant_summary

pytestmark = pytest.mark.exercise


def raw_transactions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "tx_id": ["tx_01", "tx_02", "tx_03", "tx_02", "tx_04", "tx_05", "tx_06"],
            "merchant_id": ["m_01", "m_02", "m_01", "m_02", "m_03", "m_02", "m_09"],
            "amount_minor": [2500, 1999, 48000, 1999, 120, np.nan, 7300],
            "category": ["food", "travel", "food", "travel", None, "travel", "games"],
            "is_fraud": [False, False, True, False, False, False, True],
        }
    )


def clean() -> pd.DataFrame:
    """What clean_transactions(raw_transactions()) returns - written out, so each function is tested alone."""
    return pd.DataFrame(
        {
            "tx_id": ["tx_01", "tx_02", "tx_03", "tx_04", "tx_06"],
            "merchant_id": ["m_01", "m_02", "m_01", "m_03", "m_09"],
            "amount_minor": np.array([2500, 1999, 48000, 120, 7300], dtype=np.int64),
            "category": ["food", "travel", "food", "unknown", "games"],
            "is_fraud": [False, False, True, False, True],
        }
    )


class TestCleanTransactions:
    def test_removes_duplicates_and_missing_amounts(self):
        out = clean_transactions(raw_transactions())
        assert out["tx_id"].tolist() == ["tx_01", "tx_02", "tx_03", "tx_04", "tx_06"]

    def test_amounts_are_whole_minor_units(self):
        out = clean_transactions(raw_transactions())
        assert out["amount_minor"].dtype == np.int64
        assert out["amount_minor"].tolist() == [2500, 1999, 48000, 120, 7300]

    def test_missing_category_becomes_unknown(self):
        out = clean_transactions(raw_transactions())
        assert out["category"].tolist() == ["food", "travel", "food", "unknown", "games"]

    def test_index_is_renumbered(self):
        assert clean_transactions(raw_transactions()).index.tolist() == [0, 1, 2, 3, 4]

    def test_whole_result(self):
        pd.testing.assert_frame_equal(clean_transactions(raw_transactions()), clean())

    def test_does_not_change_its_input(self):
        raw = raw_transactions()
        clean_transactions(raw)
        pd.testing.assert_frame_equal(raw, raw_transactions())


class TestMerchantSummary:
    def test_counts_totals_and_fraud_rate(self):
        out = merchant_summary(clean())
        assert out.index.name == "merchant_id"
        assert list(out.columns) == ["n", "total_minor", "fraud_rate"]
        assert out.loc["m_01"].tolist() == [2, 50500, 0.5]
        assert out.loc["m_09", "fraud_rate"] == 1.0

    def test_sorted_by_total_then_merchant(self):
        tx = pd.DataFrame(
            {
                "tx_id": ["a", "b", "c", "d"],
                "merchant_id": ["m_b", "m_a", "m_c", "m_c"],
                "amount_minor": [100, 100, 50, 300],
                "is_fraud": [False, True, False, False],
            }
        )
        assert merchant_summary(tx).index.tolist() == ["m_c", "m_a", "m_b"]


class TestAddCountry:
    merchants = pd.DataFrame({"merchant_id": ["m_01", "m_02", "m_03"], "country": ["IN", "GB", "IN"]})

    def test_keeps_every_transaction_once_in_order(self):
        tx = clean()
        out = add_country(tx, self.merchants)
        assert out["tx_id"].tolist() == tx["tx_id"].tolist()

    def test_unknown_merchant_gets_unknown_country(self):
        out = add_country(clean(), self.merchants)
        assert out["country"].tolist() == ["IN", "GB", "IN", "IN", "unknown"]

    def test_duplicate_merchant_is_an_error(self):
        dup = pd.concat([self.merchants, pd.DataFrame({"merchant_id": ["m_01"], "country": ["GB"]})])
        with pytest.raises(pd.errors.MergeError):
            add_country(clean(), dup)


class TestFlagForReview:
    def test_large_or_games_needs_review(self):
        out = flag_for_review(clean(), threshold_minor=7300)
        assert out["needs_review"].tolist() == [False, False, True, False, True]
        assert out["needs_review"].dtype == bool

    def test_threshold_is_inclusive(self):
        out = flag_for_review(clean(), threshold_minor=2500)
        assert out.loc[out["tx_id"] == "tx_01", "needs_review"].item()

    def test_does_not_change_its_input(self):
        tx = clean()
        flag_for_review(tx, threshold_minor=1)
        assert "needs_review" not in tx.columns
