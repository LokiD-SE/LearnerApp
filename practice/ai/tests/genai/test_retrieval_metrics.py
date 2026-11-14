"""Checks exercises/genai/retrieval_metrics.py: recall@k, reciprocal rank, MRR, ANN recall and an evaluation run."""

import pytest

from genai.retrieval_metrics import (
    evaluate,
    mean_reciprocal_rank,
    neighbour_recall,
    recall_at_k,
    reciprocal_rank,
)

pytestmark = pytest.mark.exercise


def test_recall_at_k_counts_relevant_ids_in_the_first_k():
    assert recall_at_k(["a02", "a07", "a03"], {"a01", "a02", "a04"}, 3) == pytest.approx(1 / 3)
    assert recall_at_k(["a01", "a02", "a09"], {"a01", "a02"}, 1) == pytest.approx(0.5)
    assert recall_at_k(["a01", "a02", "a09"], {"a01", "a02"}, 3) == 1.0
    assert recall_at_k([], {"a01"}, 3) == 0.0


def test_recall_counts_a_repeated_hit_once():
    assert recall_at_k(["a01", "a01", "a01"], {"a01", "a02"}, 3) == pytest.approx(0.5)


def test_recall_rejects_empty_relevant_and_bad_k():
    with pytest.raises(ValueError):
        recall_at_k(["a01"], set(), 3)
    with pytest.raises(ValueError):
        recall_at_k(["a01"], {"a01"}, 0)


def test_reciprocal_rank_uses_the_first_relevant_position():
    assert reciprocal_rank(["a11", "a07", "a01"], {"a07"}) == pytest.approx(0.5)
    assert reciprocal_rank(["a07", "a11"], {"a07", "a11"}) == 1.0
    assert reciprocal_rank(["a11", "a09", "a12"], {"a05", "a06"}) == 0.0
    assert reciprocal_rank(["x", "y", "z", "a05"], {"a05"}) == pytest.approx(0.25)
    assert reciprocal_rank(["x", "y", "z", "a05"], {"a05"}, k=3) == 0.0


def test_mean_reciprocal_rank():
    runs = [(["a"], {"a"}), (["x", "b"], {"b"}), (["x", "y"], {"c"})]
    assert mean_reciprocal_rank(runs) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        mean_reciprocal_rank([])


def test_neighbour_recall_compares_with_the_exact_top_k():
    assert neighbour_recall([1, 2, 3, 9], [1, 2, 3, 4], 4) == pytest.approx(0.75)
    assert neighbour_recall([3, 2, 1], [1, 2, 3, 4], 3) == 1.0
    assert neighbour_recall([5, 6], [1, 2, 3], 2) == 0.0


def test_evaluate_averages_and_lists_the_misses():
    index = {
        "refund a card payment": ["a01", "a02", "a09"],
        "when do I get paid": ["a11", "a07", "a01"],
        "forgot my login": ["a03", "a07", "a01"],
    }
    queries = [
        ("refund a card payment", {"a01", "a02"}),
        ("when do I get paid", {"a07"}),
        ("forgot my login", {"a11"}),
    ]
    result = evaluate(lambda text: index[text], queries, k=3)
    assert result["queries"] == 3
    assert result["recall@k"] == pytest.approx(2 / 3)
    assert result["mrr@k"] == pytest.approx(0.5)
    assert result["misses"] == ["forgot my login"]


def test_evaluate_only_looks_at_the_first_k():
    result = evaluate(lambda text: ["x", "y", "a01"], [("q", {"a01"})], k=2)
    assert (result["recall@k"], result["mrr@k"], result["misses"]) == (0.0, 0.0, ["q"])
