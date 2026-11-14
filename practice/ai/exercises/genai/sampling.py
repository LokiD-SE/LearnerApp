"""Turn next-token logits into a choice: temperature, top-k, top-p (nucleus) and greedy decoding.

Lesson: how-llms-work. Exercise: implement the functions marked TODO and fix the draft of top_p_filter.

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
    raise NotImplementedError  # TODO


def top_k_filter(logits: np.ndarray, k: int) -> np.ndarray:
    """Keep the ``k`` highest logits and set every other one to ``-inf``.

    ``k`` must be at least 1; a ``k`` larger than the vocabulary keeps everything. Ties at the cut are kept
    in order of token id (lower id first), so exactly ``min(k, vocab)`` tokens survive.
    """
    raise NotImplementedError  # TODO


def top_p_filter(logits: np.ndarray, p: float) -> np.ndarray:
    """Nucleus filter (Holtzman et al., 2020): keep the SMALLEST set of most probable tokens whose
    probabilities add up to at least ``p``; set every other logit to ``-inf``.

    ``p`` is in (0, 1]. The most probable token is always kept, so the result is never empty.
    """
    # Draft from a teammate - it runs, but check it against the docstring.
    z = np.asarray(logits, dtype=np.float64)
    probs = softmax(z)
    order = np.argsort(-probs, kind="stable")
    cumulative = np.cumsum(probs[order])
    keep = order[cumulative <= p]
    z[keep] = -np.inf
    return z


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
    raise NotImplementedError  # TODO
