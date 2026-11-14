"""Multi-head self-attention and a pre-norm transformer block - lesson attention-and-transformers."""

import torch
import torch.nn.functional as F
from torch import nn


class MultiHeadSelfAttention(nn.Module):
    """Self-attention with num_heads heads, laid out like nn.MultiheadAttention so weights can be copied.

    Parameters (names matter - the tests copy nn.MultiheadAttention's weights into them):
      in_proj  - nn.Linear(d_model, 3 * d_model): one matrix holding W_Q, W_K, W_V stacked in that order
      out_proj - nn.Linear(d_model, d_model): W_O
    Each head works in d_head = d_model // num_heads dimensions; d_model must be divisible by num_heads
    (raise ValueError otherwise).
    """

    def __init__(self, d_model, num_heads):
        super().__init__()
        if d_model % num_heads:
            raise ValueError(f"d_model {d_model} is not divisible by num_heads {num_heads}")
        self.d_model, self.num_heads, self.d_head = d_model, num_heads, d_model // num_heads
        self.in_proj = nn.Linear(d_model, 3 * d_model)
        self.out_proj = nn.Linear(d_model, d_model)

    def split_heads(self, t):
        """(batch, seq, d_model) -> (batch, num_heads, seq, d_head)."""
        b, n, _ = t.shape
        return t.view(b, self.num_heads, n, self.d_head)  # draft: the shape is right - are the numbers?

    def merge_heads(self, t):
        """(batch, num_heads, seq, d_head) -> (batch, seq, d_model) - the inverse of split_heads."""
        raise NotImplementedError("merge_heads")

    def forward(self, x, causal=False, key_padding_mask=None):
        """x: (batch, seq, d_model). Returns (output (batch, seq, d_model), weights (batch, heads, seq, seq)).

        causal=True: position i attends only to positions <= i.
        key_padding_mask: optional bool (batch, seq) in nn.MultiheadAttention's convention - True = PADDING,
        ignore this key.
        """
        b, n, _ = x.shape
        q, k, v = self.in_proj(x).chunk(3, dim=-1)
        q, k, v = self.split_heads(q), self.split_heads(k), self.split_heads(v)
        scores = q @ k.transpose(-2, -1) / self.d_model**0.5  # (b, h, n, n)
        # TODO: causal masking and key_padding_mask
        weights = F.softmax(scores, dim=-1)
        out = self.merge_heads(weights @ v)
        return self.out_proj(out), weights


class TransformerBlock(nn.Module):
    """Pre-norm block: x = x + attn(norm1(x)); x = x + ffn(norm2(x)).

    Attributes: norm1, attn (MultiHeadSelfAttention), norm2, ffn (nn.Sequential(Linear(d_model, d_ff),
    ReLU, Linear(d_ff, d_model))).
    """

    def __init__(self, d_model, num_heads, d_ff):
        super().__init__()
        self.norm1 = nn.LayerNorm(d_model)
        self.attn = MultiHeadSelfAttention(d_model, num_heads)
        self.norm2 = nn.LayerNorm(d_model)
        self.ffn = nn.Sequential(nn.Linear(d_model, d_ff), nn.ReLU(), nn.Linear(d_ff, d_model))

    def forward(self, x, causal=False, key_padding_mask=None):
        """x: (batch, seq, d_model) -> (batch, seq, d_model)."""
        # draft copied from the 2017 paper's layout - is that the order the docstring asks for?
        a, _ = self.attn(x, causal=causal, key_padding_mask=key_padding_mask)
        x = self.norm1(x + a)
        return self.norm2(x + self.ffn(x))
