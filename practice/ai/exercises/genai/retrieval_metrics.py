"""Measuring retrieval: recall@k, reciprocal rank / MRR, and how much of the exact top-k an approximate index finds.

``retrieved`` is a ranked list of ids (best first). ``relevant`` is the set of ids a person marked as correct
answers for the query.
"""


def recall_at_k(retrieved, relevant, k: int) -> float:
    """Share of the relevant ids that appear in the first ``k`` retrieved ids (0.0 to 1.0).

    Duplicates in ``retrieved`` count once. ``ValueError`` if ``relevant`` is empty (recall is undefined) or
    ``k < 1``.
    """
    raise NotImplementedError


def reciprocal_rank(retrieved, relevant, k: int | None = None) -> float:
    """1 / rank of the first relevant id (rank 1 = first), or 0.0 if none is in the first ``k`` (all if None)."""
    raise NotImplementedError


def mean_reciprocal_rank(runs, k: int | None = None) -> float:
    """Mean of ``reciprocal_rank`` over ``(retrieved, relevant)`` pairs. ``ValueError`` if ``runs`` is empty."""
    raise NotImplementedError


def neighbour_recall(approx, exact, k: int) -> float:
    """ANN recall: the share of the exact top-``k`` ids that the approximate top-``k`` also returned.

    This is the recall of Malkov and Yashunin (arXiv:1603.09320): "the ratio between the number of found true
    nearest neighbors and K". It needs no human labels - only the exact search's answer.
    """
    raise NotImplementedError


def evaluate(search, queries, k: int) -> dict:
    """Run ``search(text) -> ranked ids`` on every ``(text, relevant ids)`` pair and average the metrics.

    Returns ``{"queries": n, "recall@k": mean recall_at_k, "mrr@k": mean reciprocal rank within k,
    "misses": [texts whose first k results contain no relevant id]}``, in the order given.
    """
    raise NotImplementedError
