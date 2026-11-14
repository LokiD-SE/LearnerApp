"""Checks exercises/genai/hybrid_search.py - lesson retrieval-augmented-generation."""

import math

import numpy as np
import pytest
from genai.hybrid_search import BM25, dense_top_k, embed_many, hybrid_top_k, rerank, rerank_score, rrf

pytestmark = pytest.mark.exercise

DOCS = [
    "refund fails with error SP-4012 when the balance is too low",
    "a refund reaches the customer within 5 to 10 business days",
    "webhook retries use exponential backoff for up to 3 days",
    "payouts follow a 7-day rolling schedule for new accounts",
]


class TestBM25:
    def test_idf_is_the_lucene_variant(self):
        bm = BM25(DOCS)
        assert bm.idf("refund") == pytest.approx(math.log(1 + (4 - 2 + 0.5) / (2 + 0.5)))
        assert bm.idf("webhook") == pytest.approx(math.log(1 + 3.5 / 1.5))
        assert bm.idf("unknown") == pytest.approx(math.log(1 + 4.5 / 0.5))
        assert bm.idf("the") > 0  # in 2 of 4 docs: still positive, unlike the classic log((N-n+.5)/(n+.5))

    def test_score_by_hand(self):
        docs = ["cat cat dog", "dog bird", "fish"]
        bm = BM25(docs, k1=1.2, b=0.75)
        avg = (3 + 2 + 1) / 3
        idf_cat = math.log(1 + (3 - 1 + 0.5) / (1 + 0.5))
        idf_dog = math.log(1 + (3 - 2 + 0.5) / (2 + 0.5))
        norm0 = 1.2 * (1 - 0.75 + 0.75 * 3 / avg)
        expected0 = idf_cat * 2 * 2.2 / (2 + norm0) + idf_dog * 1 * 2.2 / (1 + norm0)
        norm1 = 1.2 * (1 - 0.75 + 0.75 * 2 / avg)
        expected1 = idf_dog * 2.2 / (1 + norm1)
        np.testing.assert_allclose(bm.scores("cat dog"), [expected0, expected1, 0.0])

    def test_case_and_punctuation_are_ignored_and_query_repeats_count(self):
        bm = BM25(DOCS)
        np.testing.assert_allclose(bm.scores("REFUND!"), bm.scores("refund"))
        np.testing.assert_allclose(bm.scores("refund refund"), 2 * bm.scores("refund"))

    def test_saturation_and_length_normalisation(self):
        bm = BM25(["sandpay", "sandpay sandpay sandpay sandpay sandpay sandpay", "other words here"])
        s = bm.scores("sandpay")
        assert s[1] > s[0] and s[1] < 6 * s[0]  # more occurrences help, with diminishing returns
        no_norm = BM25(["refund", "refund padding padding padding padding"], b=0.0).scores("refund")
        assert no_norm[0] == pytest.approx(no_norm[1])  # b = 0 switches length normalisation off
        with_norm = BM25(["refund", "refund padding padding padding padding"]).scores("refund")
        assert with_norm[0] > with_norm[1]

    def test_top_k_skips_zero_scores_and_breaks_ties_by_index(self):
        bm = BM25(DOCS)
        assert bm.top_k("SP-4012 refund", 3) == [0, 1]
        assert bm.top_k("refund", 1) == [1]  # shorter doc wins on length normalisation
        assert BM25(["a b", "a b", "c"]).top_k("a", 5) == [0, 1]
        assert bm.top_k("cryptocurrency", 3) == []


class TestFusion:
    def test_rrf_formula_and_order(self):
        fused = rrf([[3, 1, 2], [1, 4]], k=60)
        expected = {3: 1 / 61, 1: 1 / 62 + 1 / 61, 2: 1 / 63, 4: 1 / 62}
        assert [doc for doc, _ in fused] == [1, 3, 4, 2]
        for doc, score in fused:
            assert score == pytest.approx(expected[doc])

    def test_rrf_ties_and_k(self):
        assert [d for d, _ in rrf([[5, 2], [2, 5]])] == [2, 5]
        assert rrf([[7]], k=0)[0] == (7, pytest.approx(1.0))
        assert rrf([]) == []

    def test_dense_and_hybrid(self):
        vectors = embed_many(DOCS)
        assert dense_top_k("exponential backoff retries", vectors, 2)[0] == 2
        bm = BM25(DOCS)
        top = hybrid_top_k("refund error SP-4012", bm, vectors, 2)
        assert top[0] == 0 and len(top) == 2


class TestRerank:
    def test_score_is_coverage_plus_phrase(self):
        # content terms: dispute, fee  ("the", "is", "what" are stopwords)
        assert rerank_score("What is the dispute fee?", "a dispute fee of 15 EUR") == pytest.approx(1.0)
        assert rerank_score("What is the dispute fee?", "the fee for a dispute") == pytest.approx(0.8)
        assert rerank_score("What is the dispute fee?", "card fees") == pytest.approx(0.0)
        assert rerank_score("dispute fee", "the dispute") == pytest.approx(0.4)
        assert rerank_score("refund", "refund now") == pytest.approx(0.8)
        assert rerank_score("what is it", "anything") == 0.0

    def test_rerank_orders_candidates_and_keeps_ties_in_order(self):
        texts = ["card fees", "the dispute", "a dispute fee of 15 EUR", "dispute fee"]
        assert rerank("dispute fee", texts, [0, 1, 2, 3], 3) == [
            (2, pytest.approx(1.0)),
            (3, pytest.approx(1.0)),
            (1, pytest.approx(0.4)),
        ]
        assert [i for i, _ in rerank("dispute fee", texts, [3, 2], 2)] == [3, 2]
