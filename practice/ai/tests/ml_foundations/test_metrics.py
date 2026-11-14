"""Checks exercises/ml_foundations/metrics.py against hand-worked cases and scikit-learn's metrics."""

import numpy as np
import pytest
from sklearn import metrics as skm

from ml_foundations.metrics import (
    average_precision,
    confusion_counts,
    precision_recall_f1,
    roc_auc,
    threshold_for_recall,
)

pytestmark = pytest.mark.exercise

# A tiny hand-worked case: 10 transactions, 3 frauds.
Y_TRUE = np.array([0, 0, 1, 0, 1, 0, 0, 1, 0, 0])
Y_PRED = np.array([0, 1, 1, 0, 0, 0, 0, 1, 1, 0])
SCORES = np.array([0.10, 0.70, 0.90, 0.20, 0.40, 0.05, 0.30, 0.80, 0.60, 0.15])


def fraud_like(n=2000, seed=0):
    """About 2% fraud; scores overlap and contain ties (rounded to 2 decimals)."""
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < 0.02).astype(int)
    scores = np.round(np.clip(rng.normal(0.3 + 0.25 * y, 0.15), 0, 1), 2)
    return y, scores


def test_confusion_counts_hand_case():
    assert confusion_counts(Y_TRUE, Y_PRED) == {"tp": 2, "fp": 2, "fn": 1, "tn": 5}


def test_confusion_counts_match_sklearn_layout():
    y, s = fraud_like()
    pred = (s >= 0.5).astype(int)
    tn, fp, fn, tp = skm.confusion_matrix(y, pred).ravel()
    assert confusion_counts(y, pred) == {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def test_precision_recall_f1_hand_case():
    p, r, f1 = precision_recall_f1(Y_TRUE, Y_PRED)
    assert p == pytest.approx(2 / 4)
    assert r == pytest.approx(2 / 3)
    assert f1 == pytest.approx(2 * 0.5 * (2 / 3) / (0.5 + 2 / 3))


def test_precision_recall_f1_match_sklearn():
    y, s = fraud_like(seed=1)
    for threshold in [0.3, 0.5, 0.7]:
        pred = (s >= threshold).astype(int)
        assert precision_recall_f1(y, pred) == pytest.approx(
            (
                skm.precision_score(y, pred, zero_division=0),
                skm.recall_score(y, pred, zero_division=0),
                skm.f1_score(y, pred, zero_division=0),
            )
        )


def test_nothing_flagged_gives_zeros_not_an_error():
    # The "always genuine" model: high accuracy, but precision, recall and F1 are all 0.
    assert precision_recall_f1(Y_TRUE, np.zeros_like(Y_TRUE)) == (0.0, 0.0, 0.0)


def test_roc_auc_hand_case_and_ties():
    assert roc_auc(Y_TRUE, SCORES) == pytest.approx(skm.roc_auc_score(Y_TRUE, SCORES))
    # Every score equal: no ranking at all, so exactly 0.5.
    assert roc_auc(Y_TRUE, np.full(10, 0.4)) == pytest.approx(0.5)


def test_roc_auc_matches_sklearn_with_ties():
    y, s = fraud_like(seed=2)
    assert roc_auc(y, s) == pytest.approx(skm.roc_auc_score(y, s))


def test_roc_auc_needs_both_classes():
    with pytest.raises(ValueError):
        roc_auc(np.zeros(5), np.linspace(0, 1, 5))


def test_average_precision_hand_case():
    # Ranked: 0.90 fraud, 0.80 fraud, 0.70, 0.60, 0.40 fraud -> 1/3*1 + 1/3*1 + 1/3*(3/5)
    assert average_precision(Y_TRUE, SCORES) == pytest.approx(1 / 3 + 1 / 3 + 1 / 5)


def test_average_precision_matches_sklearn_with_ties():
    for seed in [3, 4, 5]:
        y, s = fraud_like(seed=seed)
        assert average_precision(y, s) == pytest.approx(skm.average_precision_score(y, s))


def test_random_scores_ap_is_near_the_fraud_rate_but_auc_is_near_half():
    rng = np.random.default_rng(6)
    y = (rng.random(20_000) < 0.01).astype(int)
    s = rng.random(20_000)
    assert roc_auc(y, s) == pytest.approx(0.5, abs=0.03)
    assert average_precision(y, s) == pytest.approx(y.mean(), abs=0.005)


def test_average_precision_needs_a_positive():
    with pytest.raises(ValueError):
        average_precision(np.zeros(4), np.array([0.1, 0.2, 0.3, 0.4]))


def test_threshold_for_recall_hand_case():
    # Frauds score 0.90, 0.80 and 0.40.
    assert threshold_for_recall(Y_TRUE, SCORES, 0.5) == pytest.approx(0.80)
    assert threshold_for_recall(Y_TRUE, SCORES, 2 / 3) == pytest.approx(0.80)
    assert threshold_for_recall(Y_TRUE, SCORES, 1.0) == pytest.approx(0.40)


def test_threshold_for_recall_is_the_highest_that_meets_the_target():
    y, s = fraud_like(seed=7)
    t = threshold_for_recall(y, s, 0.8)
    flagged = s >= t
    assert flagged[y == 1].mean() >= 0.8
    higher = s[s > t]
    if higher.size:
        next_up = higher.min()
        assert (s >= next_up)[y == 1].mean() < 0.8


def test_threshold_for_recall_rejects_bad_targets():
    for bad in [0, -0.1, 1.5]:
        with pytest.raises(ValueError):
            threshold_for_recall(Y_TRUE, SCORES, bad)
