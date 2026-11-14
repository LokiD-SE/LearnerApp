"""Checks exercises/ml_foundations/pca.py against scikit-learn's PCA and hand-worked cases."""

import numpy as np
import pytest
from sklearn.decomposition import PCA

from ml_foundations.pca import (
    components_for_variance,
    fit_pca,
    inverse_transform,
    reconstruction_error,
    transform,
)

pytestmark = pytest.mark.exercise


def profiles(n=300, seed=5):
    """24-hour volume shares: mixtures of three daily peaks (rows sum to 1), as in the lesson."""
    rng = np.random.default_rng(seed)
    hours = np.arange(24)
    bump = lambda c, w: np.exp(-0.5 * ((hours - c) / w) ** 2)  # noqa: E731
    shapes = np.vstack([bump(8, 1.5), bump(12.5, 1.2), bump(19, 2.0)])
    P = rng.dirichlet([2, 2, 2], size=n) @ shapes + rng.gamma(2, 0.01, size=(n, 24))
    return P / P.sum(axis=1, keepdims=True)


def correlated(n=400, seed=0):
    """Three features far from the origin, mostly along one direction."""
    rng = np.random.default_rng(seed)
    t = rng.normal(size=n)
    return np.column_stack([50 + 3 * t, 20 - 2 * t, 7 + t]) + rng.normal(scale=0.3, size=(n, 3))


def same_up_to_sign(a, b):
    for u, v in zip(a, b):
        assert abs(float(u @ v)) == pytest.approx(1.0, abs=1e-8)


def test_matches_scikit_learn_directions_and_variance():
    X = profiles()
    model = fit_pca(X, 3)
    sk = PCA(n_components=3).fit(X)
    same_up_to_sign(model.components, sk.components_)
    np.testing.assert_allclose(model.explained_variance, sk.explained_variance_, rtol=1e-8)
    np.testing.assert_allclose(model.explained_variance_ratio, sk.explained_variance_ratio_, rtol=1e-8)


def test_centres_the_data_first():
    X = correlated()
    model = fit_pca(X, 1)
    np.testing.assert_allclose(model.mean, X.mean(axis=0))
    same_up_to_sign(model.components, PCA(n_components=1).fit(X).components_)


def test_components_are_orthonormal():
    model = fit_pca(profiles(), 4)
    np.testing.assert_allclose(model.components @ model.components.T, np.eye(4), atol=1e-10)


def test_sign_convention_largest_entry_positive():
    model = fit_pca(correlated(), 3)
    for row in model.components:
        assert row[np.argmax(np.abs(row))] > 0


def test_transform_matches_scikit_learn_up_to_sign():
    X = correlated()
    model = fit_pca(X, 2)
    Z = transform(model, X)
    Zsk = PCA(n_components=2).fit_transform(X)
    for j in range(2):
        assert abs(np.corrcoef(Z[:, j], Zsk[:, j])[0, 1]) == pytest.approx(1.0)
        assert np.abs(Z[:, j]) == pytest.approx(np.abs(Zsk[:, j]))


def test_whitened_scores_have_unit_variance():
    X = profiles()
    W = transform(fit_pca(X, 2), X, whiten=True)
    np.testing.assert_allclose(W.var(axis=0, ddof=1), [1.0, 1.0], rtol=1e-8)


def test_inverse_transform_with_all_components_is_exact():
    X = correlated()
    model = fit_pca(X, 3)
    np.testing.assert_allclose(inverse_transform(model, transform(model, X)), X, atol=1e-9)


def test_reconstruction_error_flags_an_odd_profile():
    X = profiles()
    model = fit_pca(X, 2)
    night = np.exp(-0.5 * ((np.arange(24) - 2.5) / 1.0) ** 2)
    night = night / night.sum()
    errors = reconstruction_error(model, np.vstack([X, night]))
    assert errors.shape == (len(X) + 1,)
    assert np.argmax(errors) == len(X)
    assert errors[-1] > 50 * np.median(errors[:-1])


def test_reconstruction_error_matches_scikit_learn():
    X = profiles()
    sk = PCA(n_components=2).fit(X)
    expected = np.sum((X - sk.inverse_transform(sk.transform(X))) ** 2, axis=1)
    np.testing.assert_allclose(reconstruction_error(fit_pca(X, 2), X), expected, atol=1e-12)


@pytest.mark.parametrize("target", [0.5, 0.9, 0.95, 0.99])
def test_components_for_variance_matches_scikit_learn(target):
    X = profiles()
    assert components_for_variance(X, target) == PCA(n_components=target).fit(X).n_components_


def test_rejects_too_many_components():
    with pytest.raises(ValueError):
        fit_pca(correlated(), 4)
