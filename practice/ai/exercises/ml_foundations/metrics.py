"""Classification metrics from first principles, for SandPay's fraud model.

``y_true`` holds 0 (genuine) and 1 (fraud); ``y_pred`` holds hard 0/1 decisions; ``scores`` holds the
model's fraud scores (higher means more likely fraud). Use NumPy only - no ``sklearn.metrics`` - so you see
exactly what each number counts. The tests compare your results with scikit-learn's.
"""

import numpy as np


def confusion_counts(y_true, y_pred) -> dict[str, int]:
    """Return {"tp": ..., "fp": ..., "fn": ..., "tn": ...} with fraud (1) as the positive class."""
    raise NotImplementedError


def precision_recall_f1(y_true, y_pred) -> tuple[float, float, float]:
    """Precision, recall and F1 for the fraud class.

    A ratio whose denominator is 0 is 0.0 (scikit-learn's ``zero_division=0``): no fraud flagged means
    precision 0.0, no fraud in the data means recall 0.0, and F1 is 0.0 when precision + recall is 0.
    """
    raise NotImplementedError


def roc_auc(y_true, scores) -> float:
    """Area under the ROC curve: the probability that a random fraud row scores higher than a random
    genuine row, counting a tie as half. Raise ValueError if only one class is present."""
    raise NotImplementedError


def average_precision(y_true, scores) -> float:
    """Average precision as scikit-learn defines it: AP = sum over thresholds of (R_n - R_(n-1)) * P_n.

    Use every distinct score as a threshold, from the highest down; at threshold t a row is flagged when
    its score >= t. Start from recall 0. No interpolation. Raise ValueError if there is no fraud row.
    """
    raise NotImplementedError


def threshold_for_recall(y_true, scores, min_recall: float) -> float:
    """The highest score threshold (one of the scores) whose recall is at least ``min_recall``.

    Flag a row when its score >= threshold. A higher threshold flags fewer rows, so the highest one that
    still meets the recall target gives the fewest false alarms. Raise ValueError unless
    0 < min_recall <= 1, or if there is no fraud row.
    """
    raise NotImplementedError
