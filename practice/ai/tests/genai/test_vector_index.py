"""Checks exercises/genai/vector_index.py: normalising, the three metrics, top-k and a filtered exact index."""

import numpy as np
import pytest
from numpy.testing import assert_allclose
from toy_embeddings import embed, embed_many

from genai.vector_index import BruteForceIndex, normalise_rows, similarity, top_k

pytestmark = pytest.mark.exercise

DOCS = np.array([[1.0, 0.0], [3.0, 3.0], [0.6, 0.8]])
QUERY = np.array([1.0, 0.2])

ARTICLES = [
    ("a01", "How to refund a card payment", {"topic": "refunds", "region": "eu"}),
    ("a02", "Refund a card payment in the United States", {"topic": "refunds", "region": "us"}),
    ("a05", "Respond to a chargeback opened by a cardholder", {"topic": "disputes", "region": "eu"}),
    ("a08", "Change the bank account for payouts", {"topic": "payouts", "region": "us"}),
    ("a11", "Reset your dashboard password", {"topic": "account", "region": "eu"}),
]


def help_centre():
    index = BruteForceIndex(256)
    index.add([a for a, _, _ in ARTICLES], embed_many([t for _, t, _ in ARTICLES]), [m for *_, m in ARTICLES])
    return index


def test_normalise_rows_gives_unit_length_and_keeps_zero_rows():
    out = normalise_rows([[3.0, 4.0], [0.0, 0.0]])
    assert_allclose(out, [[0.6, 0.8], [0.0, 0.0]])
    assert_allclose(normalise_rows([0.0, 2.0]), [0.0, 1.0])


def test_normalise_rows_does_not_modify_the_input():
    x = np.array([[3.0, 4.0]])
    normalise_rows(x)
    assert_allclose(x, [[3.0, 4.0]])


def test_the_three_metrics_rank_raw_vectors_differently():
    assert top_k(similarity(QUERY, DOCS, "cosine"), 3).tolist() == [0, 1, 2]
    assert top_k(similarity(QUERY, DOCS, "dot"), 3).tolist() == [1, 0, 2]
    assert top_k(similarity(QUERY, DOCS, "l2"), 3).tolist() == [0, 2, 1]
    assert_allclose(similarity(QUERY, DOCS, "dot"), [1.0, 3.6, 0.76])
    assert_allclose(similarity(QUERY, DOCS, "l2"), -np.linalg.norm(DOCS - QUERY, axis=1))


def test_on_unit_vectors_the_three_metrics_agree():
    rng = np.random.default_rng(0)
    m = normalise_rows(rng.normal(size=(200, 16)))
    q = normalise_rows(rng.normal(size=16))
    cos = similarity(q, m, "cosine")
    assert_allclose(similarity(q, m, "dot"), cos)
    assert_allclose(similarity(q, m, "l2") ** 2, 2 - 2 * cos)
    assert top_k(similarity(q, m, "l2"), 10).tolist() == top_k(cos, 10).tolist()


def test_unknown_metric_is_rejected():
    with pytest.raises(ValueError):
        similarity(QUERY, DOCS, "manhattan")
    with pytest.raises(ValueError):
        BruteForceIndex(2, metric="hamming")


def test_top_k_is_best_first_with_ties_to_the_lower_position():
    assert top_k([0.2, 0.9, 0.5, 0.9, 0.1], 3).tolist() == [1, 3, 2]
    assert top_k([0.5, 0.5, 0.5], 2).tolist() == [0, 1]
    assert top_k([0.3, 0.7], 10).tolist() == [1, 0]
    with pytest.raises(ValueError):
        top_k([0.3], 0)


def test_top_k_matches_a_full_sort_on_many_scores():
    scores = np.random.default_rng(1).normal(size=5000)
    assert top_k(scores, 25).tolist() == np.argsort(-scores, kind="stable")[:25].tolist()


def test_search_returns_ids_and_cosine_scores_best_first():
    hits = help_centre().search(embed("refund a card payment"), 2)
    assert [h[0] for h in hits] == ["a01", "a02"]
    assert hits[0][1] == pytest.approx(float(embed("refund a card payment") @ embed(ARTICLES[0][1])))
    assert hits[0][1] >= hits[1][1]


def test_cosine_index_ignores_vector_length():
    index = BruteForceIndex(2)
    index.add(["short", "long"], [[1.0, 0.0], [30.0, 30.0]])
    assert index.search(np.array([1.0, 0.2]), 1)[0][0] == "short"
    dot = BruteForceIndex(2, metric="dot")
    dot.add(["short", "long"], [[1.0, 0.0], [30.0, 30.0]])
    assert dot.search(np.array([1.0, 0.2]), 1)[0][0] == "long"


def test_filter_is_applied_before_ranking_so_k_results_come_back():
    hits = help_centre().search(embed("refund a card payment"), 2, where={"region": "us"})
    assert [h[0] for h in hits] == ["a02", "a08"]
    both = help_centre().search(embed("refund a card payment"), 3, where={"region": "us", "topic": "refunds"})
    assert [h[0] for h in both] == ["a02"]
    assert help_centre().search(embed("refund"), 3, where={"region": "jp"}) == []


def test_add_validates_and_stores_nothing_on_error():
    index = help_centre()
    with pytest.raises(ValueError):
        index.add(["a01"], embed_many(["duplicate id"]))
    with pytest.raises(ValueError):
        index.add(["x1", "x1"], embed_many(["one", "two"]))
    with pytest.raises(ValueError):
        index.add(["x2"], np.ones((1, 8)))
    with pytest.raises(ValueError):
        index.add(["x3", "x4"], embed_many(["only one"]))
    assert len(index) == len(ARTICLES)


def test_query_of_the_wrong_size_is_rejected():
    with pytest.raises(ValueError):
        help_centre().search(np.ones(8), 3)
