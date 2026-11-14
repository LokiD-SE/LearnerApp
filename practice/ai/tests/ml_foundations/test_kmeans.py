"""Checks exercises/ml_foundations/kmeans.py on hand-worked cases and against scikit-learn's KMeans."""

import numpy as np
import pytest
from sklearn.cluster import KMeans
from sklearn.datasets import make_blobs
from sklearn.metrics import adjusted_rand_score

from ml_foundations.kmeans import assign, best_of, inertia, kmeans_plus_plus, lloyd, update

pytestmark = pytest.mark.exercise

# Six merchants on two scaled features: two obvious groups.
X6 = np.array([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [10.0, 10.0], [10.0, 11.0], [11.0, 10.0]])


def blobs(seed=3):
    X, y = make_blobs(n_samples=600, centers=5, cluster_std=0.7, center_box=(-10, 10), random_state=seed)
    return X, y


def test_assign_picks_the_nearest_centroid():
    centroids = np.array([[0.0, 0.0], [10.0, 10.0]])
    assert assign(X6, centroids).tolist() == [0, 0, 0, 1, 1, 1]


def test_assign_breaks_ties_towards_the_lower_index():
    assert assign(np.array([[5.0, 0.0]]), np.array([[0.0, 0.0], [10.0, 0.0]])).tolist() == [0]


def test_update_moves_centroids_to_the_means():
    new = update(X6, np.array([0, 0, 0, 1, 1, 1]), np.zeros((2, 2)))
    np.testing.assert_allclose(new, [[1 / 3, 1 / 3], [31 / 3, 31 / 3]])


def test_update_keeps_an_empty_cluster_where_it_was():
    old = np.array([[0.0, 0.0], [10.0, 10.0], [50.0, 50.0]])
    with np.errstate(all="raise"):
        new = update(X6, np.array([0, 0, 0, 1, 1, 1]), old)
    np.testing.assert_allclose(new[2], [50.0, 50.0])
    assert not np.isnan(new).any()


def test_update_does_not_change_the_old_centroids():
    old = np.zeros((2, 2))
    update(X6, np.array([0, 0, 0, 1, 1, 1]), old)
    assert not old.any()


def test_inertia_is_the_sum_of_squared_distances():
    centroids = np.array([[0.0, 0.0], [10.0, 10.0]])
    labels = np.array([0, 0, 0, 1, 1, 1])
    # each group: 0 + 1 + 1 from its corner point
    assert inertia(X6, centroids, labels) == pytest.approx(4.0)


def test_kmeans_plus_plus_returns_rows_of_x():
    X, _ = blobs()
    centres = kmeans_plus_plus(X, 5, np.random.default_rng(0))
    assert centres.shape == (5, 2)
    for c in centres:
        assert np.any(np.all(X == c, axis=1))


def test_kmeans_plus_plus_samples_in_proportion_to_squared_distance():
    # One point far away: once the first centre is in the crowd, D^2 weighting should pick it almost always.
    X = np.vstack([np.zeros((50, 2)) + np.linspace(0, 0.1, 50)[:, None], [[100.0, 100.0]]])
    rng = np.random.default_rng(1)
    picked_far = 0
    runs = 300
    for _ in range(runs):
        centres = kmeans_plus_plus(X, 2, rng)
        picked_far += np.any(np.all(centres == [100.0, 100.0], axis=1))
    assert picked_far >= 0.97 * runs


def test_kmeans_plus_plus_handles_duplicate_rows():
    X = np.ones((10, 3))
    with np.errstate(all="raise"):
        centres = kmeans_plus_plus(X, 3, np.random.default_rng(0))
    assert centres.shape == (3, 3)


def test_kmeans_plus_plus_rejects_k_larger_than_n():
    with pytest.raises(ValueError):
        kmeans_plus_plus(X6, 7, np.random.default_rng(0))


def test_lloyd_inertia_never_increases():
    X, _ = blobs(seed=8)
    _, _, history = lloyd(X, 5, np.random.default_rng(4))
    assert len(history) >= 2
    assert all(b <= a + 1e-9 for a, b in zip(history, history[1:]))


def test_lloyd_finds_the_obvious_groups():
    centroids, labels, _ = lloyd(X6, 2, np.random.default_rng(0))
    assert len(set(labels[:3])) == 1 and len(set(labels[3:])) == 1 and labels[0] != labels[3]
    assert sorted(map(tuple, np.round(centroids, 3))) == [(0.333, 0.333), (10.333, 10.333)]


def test_lloyd_labels_match_the_final_centroids():
    X, _ = blobs()
    centroids, labels, _ = lloyd(X, 5, np.random.default_rng(2))
    assert np.array_equal(labels, assign(X, centroids))


def test_lloyd_is_reproducible_with_the_same_seed():
    X, _ = blobs()
    a = lloyd(X, 5, np.random.default_rng(9))
    b = lloyd(X, 5, np.random.default_rng(9))
    np.testing.assert_array_equal(a[1], b[1])


def test_best_of_matches_scikit_learn():
    X, y = blobs()
    centroids, labels, score = best_of(X, 5, n_init=5, seed=0)
    sk = KMeans(n_clusters=5, n_init=5, random_state=0).fit(X)
    assert score == pytest.approx(sk.inertia_, rel=1e-6)
    assert adjusted_rand_score(sk.labels_, labels) == pytest.approx(1.0)
    assert adjusted_rand_score(y, labels) > 0.95


def test_best_of_is_never_worse_than_a_single_run():
    X, _ = make_blobs(n_samples=500, centers=12, cluster_std=0.6, center_box=(-12, 12), random_state=3)
    single = best_of(X, 12, n_init=1, seed=11)[2]
    many = best_of(X, 12, n_init=8, seed=11)[2]
    assert many <= single
