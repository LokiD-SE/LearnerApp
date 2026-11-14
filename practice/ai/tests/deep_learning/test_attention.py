"""Checks exercises/deep_learning/attention.py - lesson attention-and-transformers."""

import math

import pytest
import torch
import torch.nn.functional as F
from deep_learning.attention import attention, causal_mask, padding_mask

pytestmark = pytest.mark.exercise


def qkv(*shape_qk, s=None, ev=None, seed=0):
    torch.manual_seed(seed)
    *batch, L, E = shape_qk
    S = s or L
    q = torch.randn(*batch, L, E, dtype=torch.float64)
    k = torch.randn(*batch, S, E, dtype=torch.float64)
    v = torch.randn(*batch, S, ev or E, dtype=torch.float64)
    return q, k, v


class TestAttention:
    def test_hand_computed_soft_lookup(self):
        k = torch.tensor([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
        v = torch.tensor([[10.0], [20.0], [30.0]])
        q = torch.tensor([[2.0, 0.0]])
        out, w = attention(q, k, v)
        e = math.exp(2 / math.sqrt(2))
        expected = torch.tensor([[e, 1.0, e]]) / (2 * e + 1)
        torch.testing.assert_close(w, expected)
        torch.testing.assert_close(out, expected @ v)

    def test_matches_pytorch_sdpa_with_batch_and_heads(self):
        q, k, v = qkv(2, 3, 5, 8, s=7, ev=4)
        out, w = attention(q, k, v)
        assert out.shape == (2, 3, 5, 4) and w.shape == (2, 3, 5, 7)
        torch.testing.assert_close(out, F.scaled_dot_product_attention(q, k, v))
        torch.testing.assert_close(w.sum(-1), torch.ones(2, 3, 5, dtype=torch.float64))

    def test_scales_by_sqrt_of_key_dimension(self):
        q, k, v = qkv(1, 4, 64)
        out, _ = attention(q, k, v)
        unscaled = torch.softmax(q @ k.transpose(-2, -1), -1) @ v
        assert not torch.allclose(out, unscaled)
        torch.testing.assert_close(out, F.scaled_dot_product_attention(q, k, v))

    def test_boolean_mask_true_means_attend(self):
        q, k, v = qkv(2, 4, 8)
        m = torch.tensor([[True, False, True, True]]).expand(4, 4)
        out, w = attention(q, k, v, mask=m)
        assert torch.all(w[..., 1] == 0)
        torch.testing.assert_close(out, F.scaled_dot_product_attention(q, k, v, attn_mask=m))

    def test_fully_masked_row_is_zero_not_nan(self):
        q, k, v = qkv(1, 3, 4)
        m = torch.ones(3, 3, dtype=torch.bool)
        m[0] = False
        out, w = attention(q, k, v, mask=m)
        assert torch.isfinite(out).all() and torch.isfinite(w).all()
        assert torch.all(w[0, 0] == 0) and torch.all(out[0, 0] == 0)
        torch.testing.assert_close(w[0, 1:].sum(-1), torch.ones(2, dtype=torch.float64))

    def test_gradients_are_correct(self):
        q, k, v = qkv(1, 3, 4)
        for t in (q, k, v):
            t.requires_grad_(True)
        m = causal_mask(3)
        assert torch.autograd.gradcheck(lambda a, b, c: attention(a, b, c, mask=m)[0], (q, k, v))


class TestMasks:
    def test_causal_mask_values(self):
        expected = torch.tensor(
            [[1, 0, 0, 0], [1, 1, 0, 0], [1, 1, 1, 0], [1, 1, 1, 1]], dtype=torch.bool
        )
        m = causal_mask(4)
        assert m.dtype == torch.bool
        assert torch.equal(m, expected)

    def test_causal_mask_matches_is_causal(self):
        q, k, v = qkv(2, 2, 6, 8)
        out, w = attention(q, k, v, mask=causal_mask(6))
        torch.testing.assert_close(out, F.scaled_dot_product_attention(q, k, v, is_causal=True))
        assert torch.all(w.triu(1) == 0)

    def test_causal_output_ignores_the_future(self):
        q, k, v = qkv(1, 6, 8)
        out, _ = attention(q, k, v, mask=causal_mask(6))
        k2, v2 = k.clone(), v.clone()
        k2[:, 4:] += 5.0
        v2[:, 4:] -= 3.0
        out2, _ = attention(q, k2, v2, mask=causal_mask(6))
        torch.testing.assert_close(out[:, :4], out2[:, :4])
        assert not torch.allclose(out[:, 4:], out2[:, 4:])

    def test_padding_mask_values_and_shape(self):
        m = padding_mask(torch.tensor([3, 1]), 4)
        assert m.dtype == torch.bool and m.shape == (2, 1, 4)
        assert m[:, 0].tolist() == [[True, True, True, False], [True, False, False, False]]

    def test_padding_does_not_change_real_tokens(self):
        torch.manual_seed(1)
        q, k, v = qkv(1, 3, 8, seed=1)
        short, _ = attention(q, k, v)
        pad = torch.randn(1, 2, 8, dtype=torch.float64) * 10
        qp, kp, vp = (torch.cat([t, pad], 1) for t in (q, k, v))
        out, w = attention(qp, kp, vp, mask=padding_mask(torch.tensor([3]), 5))
        torch.testing.assert_close(out[:, :3], short)
        assert torch.all(w[..., 3:] == 0)

    def test_padding_and_causal_combine_with_and(self):
        q, k, v = qkv(2, 5, 4)
        m = causal_mask(5) & padding_mask(torch.tensor([5, 3]), 5)
        assert m.shape == (2, 5, 5)
        out, w = attention(q, k, v, mask=m)
        assert torch.all(w[1, :, 3:] == 0) and torch.isfinite(out).all()
