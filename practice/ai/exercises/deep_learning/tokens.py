"""Text to tensors: tokenise, build a vocabulary, encode, pad with a mask, and learn BPE merges.

Lesson: Sequence models, RNNs and word embeddings (#/lesson/sequence-models-and-embeddings) - exercise.
Reference solution: solutions/deep_learning/tokens.py. ``_merge`` at the bottom is a provided helper.
"""

import re
from collections import Counter

import torch

PAD = "<pad>"
UNK = "<unk>"
END_OF_WORD = "</w>"


def tokenize(text: str) -> list[str]:
    """Lower-case the text and split it into word tokens and single punctuation tokens.

    A word token is a run of letters, digits or underscores (the regex ``\\w+``); every other character
    that is not whitespace is a token of its own.

    >>> tokenize("Refund of EUR 12.50 failed!")
    ['refund', 'of', 'eur', '12', '.', '50', 'failed', '!']
    """
    raise NotImplementedError


def build_vocab(texts: list[str], min_freq: int = 1, max_size: int | None = None) -> dict[str, int]:
    """Map tokens to ids: PAD is 0, UNK is 1, then tokens by frequency (highest first, ties alphabetical).

    - Count tokens over every text with ``tokenize``.
    - Drop tokens seen fewer than ``min_freq`` times.
    - ``max_size`` caps the whole vocabulary, PAD and UNK included (so at least 2).
    """
    raise NotImplementedError


def encode(text: str, vocab: dict[str, int]) -> list[int]:
    """Token ids for ``text``; a token missing from the vocabulary becomes the UNK id."""
    raise NotImplementedError


def pad_batch(
    sequences: list[list[int]], pad_id: int = 0, max_len: int | None = None
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Right-pad id sequences into one batch.

    Returns ``(ids, mask, lengths)``:

    - ``ids``: int64 tensor of shape (batch, T), where T is the longest sequence (after truncation to
      ``max_len``, if given) and padding positions hold ``pad_id``;
    - ``mask``: bool tensor of the same shape, True at real tokens and False at padding;
    - ``lengths``: int64 tensor of shape (batch,), each sequence's length after truncation.

    Sequences longer than ``max_len`` keep their first ``max_len`` tokens. The input lists are not changed.
    """
    # First draft: right shapes, and it passes the happy path. Read the docstring again - where should the
    # mask come from, and what happens with max_len?
    width = max(len(s) for s in sequences)
    ids = torch.full((len(sequences), width), pad_id, dtype=torch.long)
    for row, seq in enumerate(sequences):
        ids[row, : len(seq)] = torch.tensor(seq, dtype=torch.long)
    mask = ids != 0
    lengths = mask.sum(dim=1)
    return ids, mask, lengths


def learn_bpe(word_freqs: dict[str, int], num_merges: int) -> list[tuple[str, str]]:
    """Learn byte-pair-encoding merges from word frequencies (Sennrich, Haddow and Birch, 2016).

    Each word starts as its characters plus the end-of-word symbol ``END_OF_WORD``. Repeat ``num_merges``
    times: count every adjacent symbol pair, weighted by word frequency; merge the most frequent pair
    everywhere (ties: the alphabetically smallest pair, comparing the tuples). Stop early when no pair is
    left. Returns the merges in the order they were learned.

    >>> learn_bpe({"low": 5, "lower": 2}, 2)
    [('l', 'o'), ('lo', 'w')]
    """
    raise NotImplementedError


def bpe_segment(word: str, merges: list[tuple[str, str]]) -> list[str]:
    """Split a word into subwords by applying the learned merges in order.

    Start from the characters plus ``END_OF_WORD`` and apply each merge, in the order learned, everywhere it
    occurs. The result keeps ``END_OF_WORD`` attached to the last symbol it was merged into (or on its own).

    >>> bpe_segment("lowest", [('l', 'o'), ('lo', 'w')])
    ['low', 'e', 's', 't', '</w>']
    """
    raise NotImplementedError


def _merge(symbols: tuple[str, ...], pair: tuple[str, str]) -> tuple[str, ...]:
    """Replace every non-overlapping occurrence of ``pair`` (left to right) by one joined symbol. (Provided.)"""
    out: list[str] = []
    i = 0
    while i < len(symbols):
        if i + 1 < len(symbols) and (symbols[i], symbols[i + 1]) == pair:
            out.append(symbols[i] + symbols[i + 1])
            i += 2
        else:
            out.append(symbols[i])
            i += 1
    return tuple(out)
