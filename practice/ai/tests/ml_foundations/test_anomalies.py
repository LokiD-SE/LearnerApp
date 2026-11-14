"""Checks exercises/ml_foundations/anomalies.py: Gaussian log-density, threshold choice and Isolation Forest."""

import numpy as np
import pytest
from scipy.stats import multivariate_normal
from sklearn.ensemble import IsolationForest
from sklearn.metrics import f1_score, roc_auc_score

from ml_foundations.anomalies import (
    anomaly_score,
    average_path_length,
    choose_threshold,
    fit_gaussian,
    isolation_scores,
    log_density,
)

pytestmark = pytest.mark.exercise


def transactions(n=3000, n_fraud=30, seed=11):
    """log amount, hour, km from home: genuine rows and a few 'few and different' frauds."""
    rng = np.random.default_rng(seed)
    ok = np.column_stack([rng.normal(3.4, 0.8, n), rng.normal(14, 3.5, n), np.abs(rng.normal(0, 12, n))])
    fr = np.column_stack(
        [rng.normal(5.0, 0.8, n_fraud), rng.normal(4, 2, n_fraud), np.abs(rng.normal(300, 150, n_fraud))]
    )
    return ok, fr


def test_fit_gaussian_uses_the_sample_mean_and_covariance():
    ok, _ = transactions()
    g = fit_gaussian(ok)
    np.testing.assert_allclose(g.mean, ok.mean(axis=0))
    np.testing.assert_allclose(g.cov, np.cov(ok, rowvar=False))


def test_log_density_matches_scipy():
    ok, fr = transactions()
    g = fit_gaussian(ok)
    X = np.vstack([ok[:20], fr[:5]])
    expected = multivariate_normal(mean=g.mean, cov=g.cov).logpdf(X)
    np.testing.assert_allclose(log_density(g, X), expected, rtol=1e-9)


def test_log_density_survives_rows_whose_density_underflows():
    ok, _ = transactions()
    g = fit_gaussian(ok)
    far = np.array([[30.0, 14.0, 5000.0]])
    with np.errstate(all="raise"):
        value = log_density(g, far)
    assert np.isfinite(value).all() and value[0] < -1000


def test_fraud_rows_have_lower_log_density():
    ok, fr = transactions()
    g = fit_gaussian(ok[:2000])
    scores = np.r_[log_density(g, ok[2000:]), log_density(g, fr)]
    y = np.r_[np.zeros(1000), np.ones(len(fr))]
    assert roc_auc_score(y, -scores) > 0.95


def test_choose_threshold_hand_case():
    log_dens = np.array([-30.0, -25.0, -9.0, -8.0, -12.0, -7.5])
    y = np.array([1, 1, 0, 0, 1, 0])
    assert choose_threshold(log_dens, y) == -12.0


def test_choose_threshold_picks_the_best_f1_not_the_most_frauds():
    log_dens = np.array([-20.0, -10.0, -5.0, -4.0])
    y = np.array([1, 0, 1, 0])
    # F1 = 2 TP / (flagged + frauds): -20 -> 2/3, -10 -> 0.5, -5 -> 0.8, -4 -> 2/3
    assert choose_threshold(log_dens, y) == -5.0


def test_choose_threshold_keeps_the_lowest_threshold_on_a_tie():
    # F1 = 2 TP / (flagged + frauds). -30: 2 x 1 / (1 + 2) = 2/3; -20: 2 x 2 / (4 + 2) = 2/3; -1: 4/7.
    log_dens = np.array([-30.0, -20.0, -20.0, -20.0, -1.0])
    y = np.array([1, 0, 0, 1, 0])
    assert choose_threshold(log_dens, y) == -30.0


def test_choose_threshold_maximises_f1():
    ok, fr = transactions()
    g = fit_gaussian(ok[:2000])
    lv = np.r_[log_density(g, ok[2000:]), log_density(g, fr)]
    y = np.r_[np.zeros(1000, int), np.ones(len(fr), int)]
    t = choose_threshold(lv, y)
    # F1 at every candidate threshold at once: rows flagged and frauds caught for each candidate.
    candidates = np.unique(lv)
    flagged = (lv[None, :] <= candidates[:, None]).sum(axis=1)
    caught = ((lv[None, :] <= candidates[:, None]) & (y[None, :] == 1)).sum(axis=1)
    best = np.max(2 * caught / (flagged + y.sum()))
    assert f1_score(y, (lv <= t).astype(int)) == pytest.approx(best)


def test_choose_threshold_needs_a_fraud_label():
    with pytest.raises(ValueError):
        choose_threshold(np.array([-3.0, -2.0]), np.array([0, 0]))


@pytest.mark.parametrize(
    "n, expected",
    [(1, 0.0), (2, 1.0), (256, 10.2448), (10_000, 17.5751)],
)
def test_average_path_length(n, expected):
    assert average_path_length(n) == pytest.approx(expected, abs=1e-4)


def test_anomaly_score_reference_points():
    c = average_path_length(256)
    assert anomaly_score(c, 256) == pytest.approx(0.5)
    assert anomaly_score(0.0, 256) == pytest.approx(1.0)
    np.testing.assert_allclose(anomaly_score([2.0, 12.0], 256), [0.873, 0.444], atol=1e-3)


def test_isolation_scores_point_the_right_way():
    ok, fr = transactions()
    s = isolation_scores(ok[:2000], np.vstack([ok[2000:], fr]), seed=0)
    y = np.r_[np.zeros(1000), np.ones(len(fr))]
    assert roc_auc_score(y, s) > 0.95
    assert s[len(ok) - 2000 :].mean() > s[: len(ok) - 2000].mean()


def test_isolation_scores_are_the_paper_score():
    ok, fr = transactions()
    X = np.vstack([ok[2000:2100], fr])
    expected = -IsolationForest(random_state=3).fit(ok[:2000]).score_samples(X)
    np.testing.assert_allclose(isolation_scores(ok[:2000], X, seed=3), expected)
    assert ((expected > 0) & (expected <= 1)).all()
