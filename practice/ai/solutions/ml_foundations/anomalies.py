"""Anomaly detection for SandPay card transactions: a Gaussian density model, a threshold chosen with a few
labels, and the Isolation Forest score from Liu, Ting and Zhou (2008).

Training rows are unlabelled; labels (1 = fraud) are only used to choose and check a threshold.
"""

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import IsolationForest

EULER_GAMMA = 0.5772156649


@dataclass
class Gaussian:
    mean: np.ndarray  # (d,)
    cov: np.ndarray  # (d, d), unbiased (ddof=1) like numpy.cov


def fit_gaussian(X) -> Gaussian:
    """Fit a multivariate normal to the (unlabelled) training rows."""
    X = np.asarray(X, dtype=float)
    return Gaussian(mean=X.mean(axis=0), cov=np.cov(X, rowvar=False))


def log_density(g: Gaussian, X) -> np.ndarray:
    """Log of the multivariate normal density for every row.

    log p(x) = -0.5 * ((x - mean)^T inv(cov) (x - mean) + log det(cov) + d * log(2 pi)).
    Work in logs (use ``numpy.linalg.slogdet`` and ``numpy.linalg.solve``): the density itself underflows
    to 0.0 for the rows you care about most.
    """
    X = np.asarray(X, dtype=float)
    diff = X - g.mean
    sign, logdet = np.linalg.slogdet(g.cov)
    if sign <= 0:
        raise ValueError("covariance matrix is not positive definite")
    maha = np.sum(diff * np.linalg.solve(g.cov, diff.T).T, axis=1)
    return -0.5 * (maha + logdet + X.shape[1] * np.log(2 * np.pi))


def choose_threshold(log_dens, y) -> float:
    """Choose the log-density threshold that maximises F1 on labelled validation rows.

    A row is flagged when ``log_dens <= threshold``. Try every distinct value of ``log_dens`` as a threshold;
    on a tie in F1 keep the lowest threshold (fewer rows flagged). Raise ValueError when ``y`` has no fraud.
    """
    log_dens = np.asarray(log_dens, dtype=float)
    y = np.asarray(y).astype(bool)
    if not y.any():
        raise ValueError("choosing a threshold needs at least one labelled fraud")
    best_t, best_f1 = None, -1.0
    for t in np.unique(log_dens):
        flagged = log_dens <= t
        tp = np.sum(flagged & y)
        f1 = 2 * tp / (flagged.sum() + y.sum())
        if f1 > best_f1:
            best_t, best_f1 = float(t), f1
    return best_t


def average_path_length(n) -> float:
    """c(n) from the Isolation Forest paper (eq. 1): the average path length of an unsuccessful search in a
    binary search tree of n points, 2 H(n - 1) - 2 (n - 1) / n with H(i) ~ ln(i) + Euler's constant.
    c(2) is 1 and c(1) is 0 by definition."""
    if n < 1:
        raise ValueError("n must be at least 1")
    if n == 1:
        return 0.0
    if n == 2:
        return 1.0
    return 2 * (np.log(n - 1) + EULER_GAMMA) - 2 * (n - 1) / n


def anomaly_score(mean_path_length, n) -> np.ndarray:
    """The paper's score s(x, n) = 2 ** (-E(h(x)) / c(n)): near 1 is anomalous, 0.5 is unremarkable."""
    return 2.0 ** (-np.asarray(mean_path_length, dtype=float) / average_path_length(n))


def isolation_scores(X_train, X, seed=0) -> np.ndarray:
    """Fit ``IsolationForest(random_state=seed)`` on ``X_train`` and return an anomaly score for every row of
    ``X`` where HIGHER means MORE anomalous (scikit-learn's ``score_samples`` is the opposite)."""
    forest = IsolationForest(random_state=seed).fit(X_train)
    return -forest.score_samples(X)
