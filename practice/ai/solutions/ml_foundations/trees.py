"""Exercise - how a decision tree chooses a split - lesson: Decision trees, random forests and boosting.

You implement, with NumPy only, the arithmetic a CART tree (scikit-learn's DecisionTreeClassifier and
DecisionTreeRegressor) does at every node: measure impurity, score a candidate split, find the best
threshold for one feature and the best feature, and compute the "effective alpha" that cost-complexity
pruning uses to decide which branch to cut first.

``make_fraud_data`` is provided: it builds the synthetic SandPay card payments used by the lesson.
"""

import numpy as np
import pandas as pd

CATEGORIES = ["grocery", "fuel", "travel", "electronics", "gaming", "fashion", "pharmacy", "dining"]
COUNTRIES = ["IN", "GB", "US", "DE", "SG"]


def make_fraud_data(n: int = 20000, seed: int = 0) -> tuple[pd.DataFrame, pd.Series]:
    """Provided - synthetic SandPay card payments and their fraud labels (fictional data).

    Columns: amount, card_age_days, hour (0-23), attempts_24h, merchant_category and country. Fraud follows
    thresholds and one interaction, which is the structure trees find on their own: a card younger than 30
    days used before 06:00, an amount over 400, electronics or gaming, a country other than IN, and two or
    more attempts in 24 hours. About 3.5% of payments are fraud.
    """
    rng = np.random.default_rng(seed)
    category = rng.choice(CATEGORIES, size=n, p=[0.25, 0.12, 0.1, 0.12, 0.1, 0.12, 0.09, 0.1])
    country = rng.choice(COUNTRIES, size=n, p=[0.5, 0.15, 0.15, 0.1, 0.1])
    amount = np.round(np.exp(rng.normal(4.0, 1.0, n)), 2)
    card_age = np.floor(rng.exponential(300, n))
    hour = rng.integers(0, 24, n)
    attempts = rng.poisson(0.4, n)
    logit = (
        -5.0
        + 4.0 * ((card_age < 30) & (hour < 6))
        + 2.2 * (amount > 400)
        + 1.5 * np.isin(category, ["electronics", "gaming"])
        + 0.7 * (country != "IN")
        + 1.8 * (attempts >= 2)
    )
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    X = pd.DataFrame(
        {
            "amount": amount,
            "card_age_days": card_age,
            "hour": hour,
            "attempts_24h": attempts,
            "merchant_category": category,
            "country": country,
        }
    )
    return X, pd.Series(y, name="is_fraud")


def impurity(y: np.ndarray, criterion: str = "gini") -> float:
    """Impurity of the labels or targets that reached one node.

    - ``"gini"``: sum over classes of p_k * (1 - p_k), where p_k is the share of class k in ``y``.
    - ``"entropy"``: -sum of p_k * log2(p_k) over the classes present (scikit-learn uses base 2).
    - ``"squared_error"``: the mean squared difference from the mean of ``y`` (a regression node).

    An empty ``y`` has impurity 0.0. Any other criterion raises ``ValueError``.
    """
    y = np.asarray(y)
    if criterion not in ("gini", "entropy", "squared_error"):
        raise ValueError(f"unknown criterion {criterion!r}")
    if y.size == 0:
        return 0.0
    if criterion == "squared_error":
        values = y.astype(float)
        return float(np.mean((values - values.mean()) ** 2))
    _, counts = np.unique(y, return_counts=True)
    p = counts / counts.sum()
    if criterion == "gini":
        return float(np.sum(p * (1 - p)))
    return float(-np.sum(p * np.log2(p)))


def split_impurity(y_left: np.ndarray, y_right: np.ndarray, criterion: str = "gini") -> float:
    """Impurity of a split: the children's impurities weighted by their share of the node's rows.

    G = n_left / n * H(left) + n_right / n * H(right), with n = n_left + n_right.
    """
    n_left, n_right = len(y_left), len(y_right)
    n = n_left + n_right
    return n_left / n * impurity(y_left, criterion) + n_right / n * impurity(y_right, criterion)


def best_threshold(
    x: np.ndarray, y: np.ndarray, criterion: str = "gini", min_samples_leaf: int = 1
) -> tuple[float | None, float]:
    """Best threshold for one numeric feature, as CART searches it.

    Candidate thresholds are the midpoints between consecutive distinct sorted values of ``x``; rows with
    ``x <= threshold`` go left. A candidate is allowed only if both children keep at least
    ``min_samples_leaf`` rows. Return ``(threshold, decrease)`` where decrease = impurity(y) -
    split_impurity(left, right) is the largest found; on a tie keep the smallest threshold. If no candidate
    is allowed (a constant feature, too few rows), return ``(None, 0.0)``.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y)
    parent = impurity(y, criterion)
    values = np.unique(x)
    best: tuple[float | None, float] = (None, 0.0)
    for low, high in zip(values[:-1], values[1:]):
        threshold = (low + high) / 2
        left = x <= threshold
        n_left = int(left.sum())
        if n_left < min_samples_leaf or len(x) - n_left < min_samples_leaf:
            continue
        decrease = parent - split_impurity(y[left], y[~left], criterion)
        if best[0] is None or decrease > best[1]:
            best = (float(threshold), float(decrease))
    return best


def best_split(
    X: np.ndarray, y: np.ndarray, criterion: str = "gini", min_samples_leaf: int = 1
) -> tuple[int | None, float | None, float]:
    """Best (feature, threshold, decrease) over every column of ``X``.

    Use ``best_threshold`` per column and keep the largest decrease; on a tie keep the lowest column index.
    If no column has an allowed split, return ``(None, None, 0.0)``.
    """
    X = np.asarray(X, dtype=float)
    best: tuple[int | None, float | None, float] = (None, None, 0.0)
    for j in range(X.shape[1]):
        threshold, decrease = best_threshold(X[:, j], y, criterion, min_samples_leaf)
        if threshold is None:
            continue
        if best[0] is None or decrease > best[2]:
            best = (j, threshold, decrease)
    return best


def effective_alpha(
    node_impurity: float,
    node_samples: int,
    leaf_impurities: list[float],
    leaf_samples: list[int],
    total_samples: int,
) -> float:
    """The alpha at which pruning the branch below one internal node stops being worth keeping.

    scikit-learn measures a node's cost as R(t) = (node_samples / total_samples) * node_impurity, and the
    cost of the branch T_t below it as R(T_t) = the same quantity summed over the branch's leaves. Then
    alpha_eff(t) = (R(t) - R(T_t)) / (number of leaves in T_t - 1). Cost-complexity pruning cuts the
    internal node with the smallest alpha_eff first (the "weakest link"). A branch needs at least two leaves.
    """
    if len(leaf_impurities) != len(leaf_samples) or len(leaf_samples) < 2:
        raise ValueError("a branch has at least two leaves, with one impurity and one count per leaf")
    r_node = node_samples / total_samples * node_impurity
    r_branch = sum(n / total_samples * imp for imp, n in zip(leaf_impurities, leaf_samples))
    return (r_node - r_branch) / (len(leaf_samples) - 1)
