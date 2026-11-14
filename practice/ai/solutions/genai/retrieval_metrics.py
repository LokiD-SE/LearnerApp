"""Measuring retrieval: recall@k, reciprocal rank / MRR, and how much of the exact top-k an approximate index finds.

``retrieved`` is a ranked list of ids (best first). ``relevant`` is the set of ids a person marked as correct
answers for the query.
"""


def recall_at_k(retrieved, relevant, k: int) -> float:
    """Share of the relevant ids that appear in the first ``k`` retrieved ids (0.0 to 1.0).

    Duplicates in ``retrieved`` count once. ``ValueError`` if ``relevant`` is empty (recall is undefined) or
    ``k < 1``.
    """
    relevant = set(relevant)
    if not relevant:
        raise ValueError("relevant must not be empty")
    if k < 1:
        raise ValueError(f"k must be at least 1, got {k}")
    return len(set(list(retrieved)[:k]) & relevant) / len(relevant)


def reciprocal_rank(retrieved, relevant, k: int | None = None) -> float:
    """1 / rank of the first relevant id (rank 1 = first), or 0.0 if none is in the first ``k`` (all if None)."""
    relevant = set(relevant)
    ranked = list(retrieved) if k is None else list(retrieved)[:k]
    for rank, item in enumerate(ranked, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def mean_reciprocal_rank(runs, k: int | None = None) -> float:
    """Mean of ``reciprocal_rank`` over ``(retrieved, relevant)`` pairs. ``ValueError`` if ``runs`` is empty."""
    runs = list(runs)
    if not runs:
        raise ValueError("runs must not be empty")
    return sum(reciprocal_rank(r, rel, k) for r, rel in runs) / len(runs)


def neighbour_recall(approx, exact, k: int) -> float:
    """ANN recall: the share of the exact top-``k`` ids that the approximate top-``k`` also returned.

    This is the recall of Malkov and Yashunin (arXiv:1603.09320): "the ratio between the number of found true
    nearest neighbors and K". It needs no human labels - only the exact search's answer.
    """
    truth = list(exact)[:k]
    if not truth:
        raise ValueError("exact must not be empty")
    return len(set(list(approx)[:k]) & set(truth)) / len(truth)


def evaluate(search, queries, k: int) -> dict:
    """Run ``search(text) -> ranked ids`` on every ``(text, relevant ids)`` pair and average the metrics.

    Returns ``{"queries": n, "recall@k": mean recall_at_k, "mrr@k": mean reciprocal rank within k,
    "misses": [texts whose first k results contain no relevant id]}``, in the order given.
    """
    queries = list(queries)
    if not queries:
        raise ValueError("queries must not be empty")
    recalls, rrs, misses = [], [], []
    for text, relevant in queries:
        ranked = list(search(text))
        recalls.append(recall_at_k(ranked, relevant, k))
        rr = reciprocal_rank(ranked, relevant, k)
        rrs.append(rr)
        if rr == 0.0:
            misses.append(text)
    return {
        "queries": len(queries),
        "recall@k": sum(recalls) / len(recalls),
        "mrr@k": sum(rrs) / len(rrs),
        "misses": misses,
    }
