"""Checks exercises/agents/memory_store.py - lesson agent-memory-and-context."""

import numpy as np
import pytest
from agents.memory_store import MemoryStore
from toy_embeddings import embed

pytestmark = pytest.mark.exercise

QUERY = "When is my next payout? What is the payout schedule?"
# Synthetic memories of a SandPay merchant-support agent (fictional), written at the given hour.
DATA = [
    (0, "Merchant m-204 prefers replies in Spanish", 8, "semantic"),
    (2, "Merchant m-204 asked about the payout schedule for weekly payouts", 3, "episodic"),
    (30, "Refund dispute D-77 for merchant m-204 was escalated to the risk team", 9, "episodic"),
    (70, "Merchant m-204 said the payout schedule page was confusing", 4, "episodic"),
    (95, "Merchant m-204 uploaded a new logo", 1, "episodic"),
]


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def build():
    clock = Clock()
    store = MemoryStore(clock=clock)
    for hour, text, importance, kind in DATA:
        clock.now = hour
        store.add("m-204", text, importance, kind)
    store.add("m-311", "Merchant m-311 payout schedule moved to daily", 6, "semantic")
    clock.now = 100.0
    return store, clock


def ids(results):
    return [r["memory"].id for r in results]


class TestAdd:
    def test_fields(self):
        clock = Clock()
        clock.now = 7.5
        store = MemoryStore(clock=clock)
        m = store.add("m-204", "Prefers Spanish", 8, "semantic", source="operator")
        assert (m.id, m.user_id, m.kind, m.importance, m.source) == (1, "m-204", "semantic", 8, "operator")
        assert m.created_at == m.last_accessed == 7.5
        np.testing.assert_allclose(m.vector, embed("Prefers Spanish"))
        assert store.add("m-204", "x", 1).id == 2 and len(store) == 2

    @pytest.mark.parametrize("importance", [0, 11, -3])
    def test_importance_range(self, importance):
        with pytest.raises(ValueError):
            MemoryStore(clock=Clock()).add("u", "x", importance)

    def test_kind(self):
        with pytest.raises(ValueError):
            MemoryStore(clock=Clock()).add("u", "x", 5, kind="procedural")


class TestRetrieve:
    def test_paper_weights(self):
        store, _ = build()
        res = store.retrieve("m-204", QUERY, k=3)
        assert ids(res) == [4, 3, 5]
        assert [round(r["score"], 3) for r in res] == [2.064, 1.45, 1.184]
        top = res[0]
        assert (round(top["recency"], 2), round(top["importance"], 2), round(top["relevance"], 2)) == (0.69, 0.38, 1.0)

    def test_relevance_only(self):
        store, _ = build()
        assert ids(store.retrieve("m-204", QUERY, k=3, weights=(0, 0, 1))) == [4, 2, 3]

    def test_recency_only(self):
        store, _ = build()
        assert ids(store.retrieve("m-204", QUERY, k=2, weights=(1, 0, 0))) == [5, 4]

    def test_only_the_users_memories(self):
        store, _ = build()
        assert 6 not in ids(store.retrieve("m-204", QUERY, k=10))
        assert ids(store.retrieve("m-311", QUERY, k=10)) == [6]
        assert store.retrieve("nobody", QUERY) == []

    def test_min_relevance_filters_before_scaling(self):
        store, _ = build()
        assert ids(store.retrieve("m-204", QUERY, k=3, min_relevance=0.2)) == [4]
        assert store.retrieve("m-204", QUERY, min_relevance=0.9) == []

    def test_single_candidate_scores_zero(self):
        store, _ = build()
        (only,) = store.retrieve("m-311", QUERY)
        assert only["score"] == 0.0

    def test_retrieval_refreshes_recency(self):
        store, clock = build()
        store.retrieve("m-204", QUERY, k=1)  # returns memory 4
        by_id = {m.id: m for m in store._memories}
        assert by_id[4].last_accessed == 100.0
        assert by_id[2].last_accessed == 2.0
        clock.now = 101.0
        res = store.retrieve("m-204", QUERY, k=5, weights=(1, 0, 0))
        assert ids(res)[0] == 4  # retrieved an hour ago - the most recent now

    def test_ties_break_by_lower_id(self):
        clock = Clock()
        store = MemoryStore(clock=clock)
        for _ in range(3):
            store.add("u", "same text", 5)
        assert ids(store.retrieve("u", "same text", k=3)) == [1, 2, 3]

    def test_custom_embedding_and_decay(self):
        clock = Clock()
        vectors = {"a": np.array([1.0, 0.0]), "b": np.array([0.0, 1.0]), "q": np.array([0.6, 0.8])}
        store = MemoryStore(clock=clock, embed_fn=vectors.__getitem__, decay=0.5)
        store.add("u", "a", 5)
        clock.now = 1.0
        store.add("u", "b", 5)
        clock.now = 2.0
        res = store.retrieve("u", "q", k=2)
        assert ids(res) == [2, 1]
        assert res[0]["score"] == pytest.approx(2.0)
        assert res[1]["score"] == pytest.approx(0.0)


class TestForgetAndExpire:
    def test_forget_all_for_one_user(self):
        store, _ = build()
        assert store.forget("m-204") == 5
        assert len(store) == 1
        assert store.retrieve("m-204", QUERY) == []

    def test_forget_one(self):
        store, _ = build()
        assert store.forget("m-204", 3) == 1
        assert 3 not in ids(store.retrieve("m-204", QUERY, k=10))

    def test_cannot_forget_another_users_memory(self):
        store, _ = build()
        assert store.forget("m-204", 6) == 0
        assert len(store) == 6

    def test_expire_idle(self):
        store, _ = build()
        store.retrieve("m-204", QUERY, k=1)  # memory 4 accessed at 100
        assert store.expire(max_idle_hours=30) == 3  # idle hours: 100, 98, 70, 0, 5, 5
        remaining = {m.id for m in store._memories}
        assert remaining == {4, 5, 6}

    def test_expire_boundary_kept(self):
        store, _ = build()
        assert store.expire(max_idle_hours=100) == 0
        assert store.expire(max_idle_hours=99.9) == 1
