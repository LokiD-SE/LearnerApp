"""Classification metrics from first principles, for SandPay's fraud model.

``y_true`` holds 0 (genuine) and 1 (fraud); ``y_pred`` holds hard 0/1 decisions; ``scores`` holds the
model's fraud scores (higher means more likely fraud). Use NumPy only - no ``sklearn.metrics`` - so you see
exactly what each number counts. The tests compare your results with scikit-learn's.
"""

import numpy as np


def confusion_counts(y_true, y_pred) -> dict[str, int]:
    """Return {"tp": ..., "fp": ..., "fn": ..., "tn": ...} with fraud (1) as the positive class."""
    t = np.asarray(y_true).astype(bool)
    p = np.asarray(y_pred).astype(bool)
    return {
        "tp": int(np.sum(t & p)),
        "fp": int(np.sum(~t & p)),
        "fn": int(np.sum(t & ~p)),
        "tn": int(np.sum(~t & ~p)),
    }


def precision_recall_f1(y_true, y_pred) -> tuple[float, float, float]:
    """Precision, recall and F1 for the fraud class.

    A ratio whose denominator is 0 is 0.0 (scikit-learn's ``zero_division=0``): no fraud flagged means
    precision 0.0, no fraud in the data means recall 0.0, and F1 is 0.0 when precision + recall is 0.
    """
    c = confusion_counts(y_true, y_pred)
    flagged = c["tp"] + c["fp"]
    actual = c["tp"] + c["fn"]
    precision = c["tp"] / flagged if flagged else 0.0
    recall = c["tp"] / actual if actual else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def roc_auc(y_true, scores) -> float:
    """Area under the ROC curve: the probability that a random fraud row scores higher than a random
    genuine row, counting a tie as half. Raise ValueError if only one class is present."""
    t = np.asarray(y_true).astype(bool)
    s = np.asarray(scores, dtype=float)
    pos, neg = s[t], s[~t]
    if len(pos) == 0 or len(neg) == 0:
        raise ValueError("ROC AUC needs both classes in y_true")
    # Compare every positive with every negative (fine for test-sized data; ranks scale better).
    diff = pos[:, None] - neg[None, :]
    wins = np.sum(diff > 0) + 0.5 * np.sum(diff == 0)
    return float(wins / (len(pos) * len(neg)))


def average_precision(y_true, scores) -> float:
    """Average precision as scikit-learn defines it: AP = sum over thresholds of (R_n - R_(n-1)) * P_n.

    Use every distinct score as a threshold, from the highest down; at threshold t a row is flagged when
    its score >= t. Start from recall 0. No interpolation. Raise ValueError if there is no fraud row.
    """
    t = np.asarray(y_true).astype(bool)
    s = np.asarray(scores, dtype=float)
    total_pos = int(t.sum())
    if total_pos == 0:
        raise ValueError("average precision needs at least one positive")
    ap, prev_recall = 0.0, 0.0
    for threshold in np.unique(s)[::-1]:
        flagged = s >= threshold
        tp = int(np.sum(flagged & t))
        precision = tp / int(flagged.sum())
        recall = tp / total_pos
        ap += (recall - prev_recall) * precision
        prev_recall = recall
    return float(ap)


def threshold_for_recall(y_true, scores, min_recall: float) -> float:
    """The highest score threshold (one of the scores) whose recall is at least ``min_recall``.

    Flag a row when its score >= threshold. A higher threshold flags fewer rows, so the highest one that
    still meets the recall target gives the fewest false alarms. Raise ValueError unless
    0 < min_recall <= 1, or if there is no fraud row.
    """
    if not 0 < min_recall <= 1:
        raise ValueError("min_recall must be in (0, 1]")
    t = np.asarray(y_true).astype(bool)
    s = np.asarray(scores, dtype=float)
    total_pos = int(t.sum())
    if total_pos == 0:
        raise ValueError("needs at least one positive")
    for threshold in np.unique(s)[::-1]:
        if np.sum((s >= threshold) & t) / total_pos >= min_recall:
            return float(threshold)
    raise AssertionError("unreachable: the lowest score flags every row")
