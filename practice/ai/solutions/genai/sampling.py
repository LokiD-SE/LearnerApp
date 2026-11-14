"""Turn next-token logits into a choice: temperature, top-k, top-p (nucleus) and greedy decoding.

Lesson: how-llms-work. Reference solution.

Logits are a 1-D NumPy array, one score per vocabulary entry. Filters return a NEW array in which the
removed tokens have the logit ``-inf`` (so their softmax probability is exactly 0); they never change their
input. Ties are broken by the lower token id, so every function is deterministic.
"""

import numpy as np


def softmax(logits: np.ndarray) -> np.ndarray:
    """Probabilities from logits; ``-inf`` entries get probability 0. (Provided.)"""
    z = np.asarray(logits, dtype=np.float64)
    e = np.exp(z - z.max())
    return e / e.sum()


def apply_temperature(logits: np.ndarray, temperature: float) -> np.ndarray:
    """Divide the logits by ``temperature`` (> 0). Below 1 sharpens the distribution, above 1 flattens it.

    Raises ``ValueError`` for a temperature of 0 or less (greedy decoding is handled by ``sample_next``).
    """
    if temperature <= 0:
        raise ValueError("temperature must be > 0; use temperature=0 in sample_next for greedy decoding")
    return np.asarray(logits, dtype=np.float64) / temperature


def top_k_filter(logits: np.ndarray, k: int) -> np.ndarray:
    """Keep the ``k`` highest logits and set every other one to ``-inf``.

    ``k`` must be at least 1; a ``k`` larger than the vocabulary keeps everything. Ties at the cut are kept
    in order of token id (lower id first), so exactly ``min(k, vocab)`` tokens survive.
    """
    if k < 1:
        raise ValueError("k must be at least 1")
    z = np.asarray(logits, dtype=np.float64)
    order = np.argsort(-z, kind="stable")
    out = np.full_like(z, -np.inf)
    keep = order[:k]
    out[keep] = z[keep]
    return out


def top_p_filter(logits: np.ndarray, p: float) -> np.ndarray:
    """Nucleus filter (Holtzman et al., 2020): keep the SMALLEST set of most probable tokens whose
    probabilities add up to at least ``p``; set every other logit to ``-inf``.

    ``p`` is in (0, 1]. The most probable token is always kept, so the result is never empty.
    """
    if not 0 < p <= 1:
        raise ValueError("p must be in (0, 1]")
    z = np.asarray(logits, dtype=np.float64)
    probs = softmax(z)
    order = np.argsort(-probs, kind="stable")
    cumulative = np.cumsum(probs[order])
    n_keep = int(np.searchsorted(cumulative, p - 1e-12)) + 1   # first index where the sum reaches p
    keep = order[: min(n_keep, len(z))]
    out = np.full_like(z, -np.inf)
    out[keep] = z[keep]
    return out


def sample_next(
    logits: np.ndarray,
    rng: np.random.Generator,
    temperature: float = 1.0,
    top_k: int | None = None,
    top_p: float | None = None,
) -> int:
    """Pick the next token id.

    - ``temperature == 0``: greedy - return the id of the highest logit (lowest id on a tie); ``rng`` is not used.
    - Otherwise apply, in this order: temperature, then ``top_k`` (if given), then ``top_p`` (if given), turn
      the result into probabilities with ``softmax`` and draw ONE id with ``rng.choice(len(probs), p=probs)``.
    """
    z = np.asarray(logits, dtype=np.float64)
    if temperature == 0:
        return int(np.argmax(z))
    z = apply_temperature(z, temperature)
    if top_k is not None:
        z = top_k_filter(z, top_k)
    if top_p is not None:
        z = top_p_filter(z, top_p)
    probs = softmax(z)
    return int(rng.choice(len(probs), p=probs))
