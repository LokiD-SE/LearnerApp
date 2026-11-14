"""Checks exercises/genai/ivf_index.py: inverted lists, probing and recall against exact search."""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from genai.ivf_index import IVFIndex, nearest_centroids, normalise_rows

pytestmark = pytest.mark.exercise


def clustered(n=3000, d=16, topics=30, seed=7):
    rng = np.random.default_rng(seed)
    centres = rng.normal(size=(topics, d))
    return normalise_rows(centres[rng.integers(topics, size=n)] + rng.normal(scale=1.0, size=(n, d)))


def exact_top(data, q, k):
    scores = data @ q
    return np.lexsort((np.arange(len(scores)), -scores))[:k].tolist()


@pytest.fixture(scope="module")
def built():
    data = clustered()
    index = IVFIndex(n_lists=40, seed=0, n_iter=10)
    index.train(data[:2000])
    index.add(list(range(2800)), data[:2800])
    return index, data[:2800], data[2800:]


def test_nearest_centroids_orders_by_distance_with_ties_to_the_lower_index():
    c = np.array([[0.0, 0.0], [10.0, 0.0], [4.0, 0.0]])
    assert nearest_centroids(np.array([[5.0, 0.0]]), c, 3).tolist() == [[2, 0, 1]]
    assert nearest_centroids(np.array([[9.0, 0.0], [0.5, 0.0]]), c, 2).tolist() == [[1, 2], [0, 2]]
    assert nearest_centroids(np.array([[5.0, 0.0]]), c[:2], 2).tolist() == [[0, 1]]


def test_every_vector_is_in_exactly_one_list_its_nearest_centroid(built):
    index, data, _ = built
    together = np.sort(np.concatenate(index.lists))
    assert together.tolist() == list(range(len(data)))
    cells = nearest_centroids(data, index.centroids, 1)[:, 0]
    for j, members in enumerate(index.lists):
        assert (cells[members] == j).all()


def test_scanning_every_list_equals_exact_search(built):
    index, data, queries = built
    for q in queries[:20]:
        hits = index.search(q, 10, nprobe=index.n_lists)
        assert [h[0] for h in hits] == exact_top(data, q, 10)
        assert_allclose([h[1] for h in hits], np.sort(data @ q)[::-1][:10])
        assert index.last_scanned == len(data)


def test_one_probe_scans_only_the_nearest_list(built):
    index, _, queries = built
    q = queries[0]
    cell = nearest_centroids(q[None, :], index.centroids, 1)[0, 0]
    hits = index.search(q, 5, nprobe=1)
    assert index.last_scanned == len(index.lists[cell])
    assert {h[0] for h in hits} <= set(index.lists[cell].tolist())


def test_more_probes_scan_more_and_never_lower_mean_recall(built):
    index, data, queries = built
    previous_recall, previous_scanned = -1.0, 0
    for nprobe in (1, 4, 16):
        recalls, scanned = [], []
        for q in queries:
            got = {h[0] for h in index.search(q, 10, nprobe=nprobe)}
            recalls.append(len(got & set(exact_top(data, q, 10))) / 10)
            scanned.append(index.last_scanned)
        assert np.mean(recalls) >= previous_recall
        assert np.mean(scanned) > previous_scanned
        previous_recall, previous_scanned = np.mean(recalls), np.mean(scanned)
    assert previous_recall > 0.9
    assert previous_scanned < 0.6 * len(data)


def test_queries_are_normalised_like_the_stored_vectors(built):
    index, _, queries = built
    scaled, plain = index.search(queries[0] * 7.5, 5, nprobe=3), index.search(queries[0], 5, nprobe=3)
    assert [h[0] for h in scaled] == [h[0] for h in plain]
    assert_allclose([h[1] for h in scaled], [h[1] for h in plain])
    assert all(-1.0 - 1e-9 <= h[1] <= 1.0 + 1e-9 for h in scaled)


def test_nprobe_is_capped_and_validated(built):
    index, _, queries = built
    assert index.search(queries[1], 3, nprobe=999) == index.search(queries[1], 3, nprobe=index.n_lists)
    with pytest.raises(ValueError):
        index.search(queries[1], 3, nprobe=0)


def test_untrained_index_refuses_to_add():
    with pytest.raises(RuntimeError):
        IVFIndex(n_lists=4).add([1], np.ones((1, 4)))
