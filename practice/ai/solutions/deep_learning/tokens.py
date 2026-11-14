"""Text to tensors: tokenise, build a vocabulary, encode, pad with a mask, and learn BPE merges.

Lesson: sequence-models-and-embeddings. Reference solution.
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
    return re.findall(r"\w+|[^\w\s]", text.lower())


def build_vocab(texts: list[str], min_freq: int = 1, max_size: int | None = None) -> dict[str, int]:
    """Map tokens to ids: PAD is 0, UNK is 1, then tokens by frequency (highest first, ties alphabetical).

    - Count tokens over every text with ``tokenize``.
    - Drop tokens seen fewer than ``min_freq`` times.
    - ``max_size`` caps the whole vocabulary, PAD and UNK included (so at least 2).
    """
    if max_size is not None and max_size < 2:
        raise ValueError("max_size must leave room for PAD and UNK")
    counts = Counter(token for text in texts for token in tokenize(text))
    ranked = sorted((t for t, c in counts.items() if c >= min_freq), key=lambda t: (-counts[t], t))
    if max_size is not None:
        ranked = ranked[: max_size - 2]
    vocab = {PAD: 0, UNK: 1}
    for token in ranked:
        vocab[token] = len(vocab)
    return vocab


def encode(text: str, vocab: dict[str, int]) -> list[int]:
    """Token ids for ``text``; a token missing from the vocabulary becomes the UNK id."""
    unk = vocab[UNK]
    return [vocab.get(token, unk) for token in tokenize(text)]


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
    trimmed = [list(s[:max_len]) if max_len is not None else list(s) for s in sequences]
    lengths = torch.tensor([len(s) for s in trimmed], dtype=torch.long)
    width = int(lengths.max()) if len(trimmed) else 0
    ids = torch.full((len(trimmed), width), pad_id, dtype=torch.long)
    for row, seq in enumerate(trimmed):
        ids[row, : len(seq)] = torch.tensor(seq, dtype=torch.long)
    mask = torch.arange(width)[None, :] < lengths[:, None]
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
    words = {tuple(word) + (END_OF_WORD,): freq for word, freq in word_freqs.items()}
    merges: list[tuple[str, str]] = []
    for _ in range(num_merges):
        pairs: Counter[tuple[str, str]] = Counter()
        for symbols, freq in words.items():
            for pair in zip(symbols, symbols[1:]):
                pairs[pair] += freq
        if not pairs:
            break
        best = min(pairs, key=lambda p: (-pairs[p], p))
        merges.append(best)
        words = {_merge(symbols, best): freq for symbols, freq in words.items()}
    return merges


def bpe_segment(word: str, merges: list[tuple[str, str]]) -> list[str]:
    """Split a word into subwords by applying the learned merges in order.

    Start from the characters plus ``END_OF_WORD`` and apply each merge, in the order learned, everywhere it
    occurs. The result keeps ``END_OF_WORD`` attached to the last symbol it was merged into (or on its own).

    >>> bpe_segment("lowest", [('l', 'o'), ('lo', 'w')])
    ['low', 'e', 's', 't', '</w>']
    """
    symbols = tuple(word) + (END_OF_WORD,)
    for pair in merges:
        symbols = _merge(symbols, pair)
    return list(symbols)


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
