"""Next-token prediction from first principles: training pairs, a bigram model, loss, perplexity and an
autoregressive generation loop with a fixed context window.

Lesson: how-llms-work. Reference solution.

Token ids are plain ints. ``next_probs`` callables take the visible window (a list of ids) and return a
1-D NumPy array of probabilities over the vocabulary - a stand-in for a real language model.
"""

from typing import Callable

import numpy as np


def make_training_pairs(ids: list[int], context: int) -> tuple[np.ndarray, np.ndarray]:
    """Cut one long token sequence into (input, target) windows for next-token training.

    Window ``i`` is ``X[i] = ids[i : i + context]`` and its targets are the SAME window shifted one token to
    the right, ``Y[i] = ids[i + 1 : i + 1 + context]`` - so position ``j`` of ``X[i]`` is trained to predict
    ``Y[i][j]``, the token that follows it. Returns two int64 arrays of shape ``(len(ids) - context, context)``.

    Raises ``ValueError`` when ``context < 1`` or the sequence has no more than ``context`` tokens.
    """
    if context < 1:
        raise ValueError("context must be at least 1")
    if len(ids) <= context:
        raise ValueError("need more than `context` tokens")
    a = np.asarray(ids, dtype=np.int64)
    n = len(a) - context
    X = np.stack([a[i : i + context] for i in range(n)])
    Y = np.stack([a[i + 1 : i + 1 + context] for i in range(n)])
    return X, Y


def bigram_probs(ids: list[int], vocab_size: int, alpha: float = 1.0) -> np.ndarray:
    """A bigram language model: ``P[a, b]`` = probability that token ``b`` follows token ``a``.

    Count every adjacent pair ``(ids[t], ids[t + 1])``, add ``alpha`` to every cell (add-alpha smoothing, so
    an unseen pair is not impossible), and normalise each row to sum to 1. Shape ``(vocab_size, vocab_size)``.
    """
    counts = np.full((vocab_size, vocab_size), float(alpha))
    for a, b in zip(ids[:-1], ids[1:]):
        counts[a, b] += 1
    return counts / counts.sum(axis=1, keepdims=True)


def cross_entropy(probs: np.ndarray, targets: list[int]) -> float:
    """Mean negative natural log of the probability each row gave to its target token.

    ``probs`` has shape ``(n, vocab)``; ``targets`` has ``n`` ids. This is the pretraining loss, in nats.
    """
    p = np.asarray(probs, dtype=np.float64)
    t = np.asarray(targets, dtype=np.int64)
    return float(-np.log(p[np.arange(len(t)), t]).mean())


def perplexity(loss: float) -> float:
    """``exp(loss)``: the size of a uniform choice that would be equally surprised (loss in nats)."""
    return float(np.exp(loss))


def generate(
    next_probs: Callable[[list[int]], np.ndarray],
    prompt_ids: list[int],
    max_new_tokens: int,
    context: int,
    rng: np.random.Generator | None = None,
    stop_id: int | None = None,
) -> list[int]:
    """Autoregressive generation: predict one token, append it, repeat.

    - Each step calls ``next_probs`` with only the LAST ``context`` ids of prompt + generated so far (the
      model's context window); older tokens are invisible to it.
    - ``rng is None``: greedy (``argmax``, lowest id on a tie). Otherwise draw with
      ``rng.choice(len(probs), p=probs)``.
    - Stop after ``max_new_tokens`` tokens, or right after emitting ``stop_id`` (which is included).

    Returns only the NEW ids, not the prompt. The prompt list is not modified.
    """
    seq = list(prompt_ids)
    new: list[int] = []
    for _ in range(max_new_tokens):
        probs = np.asarray(next_probs(seq[-context:]), dtype=np.float64)
        token = int(np.argmax(probs)) if rng is None else int(rng.choice(len(probs), p=probs))
        seq.append(token)
        new.append(token)
        if stop_id is not None and token == stop_id:
            break
    return new
