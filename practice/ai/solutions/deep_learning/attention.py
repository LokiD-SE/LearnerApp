"""Scaled dot-product attention and its masks - lesson attention-and-transformers.

Shapes follow torch.nn.functional.scaled_dot_product_attention: queries (..., L, E), keys (..., S, E),
values (..., S, Ev). Boolean masks here use the SDPA convention - True means "may attend" - which is the
OPPOSITE of nn.MultiheadAttention's masks, where True means "blocked".
"""

import math

import torch


def attention(q, k, v, mask=None):
    """Return (output, weights) for softmax(q @ k^T / sqrt(E)) @ v.

    q: (..., L, E), k: (..., S, E), v: (..., S, Ev). mask: optional boolean tensor broadcastable to
    (..., L, S); True = this query may attend to this key, False = blocked (score set to -inf before
    the softmax). A query row whose keys are ALL blocked gets weights of 0 and an output of 0 (not NaN).
    weights has shape (..., L, S) and each row that is not fully blocked sums to 1; output is (..., L, Ev).
    Do not call torch.nn.functional.scaled_dot_product_attention - write the steps.
    """
    scores = q @ k.transpose(-2, -1) / math.sqrt(q.size(-1))
    if mask is not None:
        scores = scores.masked_fill(~mask, float("-inf"))
    weights = torch.softmax(scores, dim=-1)
    if mask is not None:
        # a fully blocked row is softmax(all -inf) = NaN; make it 0 instead
        weights = torch.nan_to_num(weights, nan=0.0)
    return weights @ v, weights


def causal_mask(n, device=None):
    """Boolean (n, n) mask, True where query i may attend to key j, i.e. j <= i (lower triangle)."""
    return torch.ones(n, n, dtype=torch.bool, device=device).tril()


def padding_mask(lengths, max_len):
    """Boolean (batch, 1, max_len) mask from sequence lengths: True for real tokens, False for padding.

    The middle dimension of 1 lets it broadcast over the query positions of a (batch, L, S) score matrix.
    Example: lengths [3, 1], max_len 4 -> [[[T, T, T, F]], [[T, F, F, F]]].
    """
    lengths = torch.as_tensor(lengths)
    keep = torch.arange(max_len, device=lengths.device)[None, :] < lengths[:, None]
    return keep[:, None, :]
