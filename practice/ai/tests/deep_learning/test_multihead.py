"""Checks exercises/deep_learning/multihead.py - lesson attention-and-transformers."""

import pytest
import torch
from deep_learning.multihead import MultiHeadSelfAttention, TransformerBlock
from torch import nn

pytestmark = pytest.mark.exercise


def pair(d=8, h=2, seed=0):
    torch.manual_seed(seed)
    ref = nn.MultiheadAttention(d, h, batch_first=True, dtype=torch.float64)
    mine = MultiHeadSelfAttention(d, h).double()
    with torch.no_grad():
        mine.in_proj.weight.copy_(ref.in_proj_weight)
        mine.in_proj.bias.copy_(ref.in_proj_bias)
        mine.out_proj.weight.copy_(ref.out_proj.weight)
        mine.out_proj.bias.copy_(ref.out_proj.bias)
    x = torch.randn(3, 5, d, dtype=torch.float64)
    return ref, mine, x


class TestMultiHeadSelfAttention:
    def test_parameter_layout_and_count(self):
        m = MultiHeadSelfAttention(16, 4)
        assert m.in_proj.weight.shape == (48, 16) and m.out_proj.weight.shape == (16, 16)
        assert sum(p.numel() for p in m.parameters()) == 4 * 16 * 16 + 4 * 16
        assert m.d_head == 4

    def test_rejects_indivisible_heads(self):
        with pytest.raises(ValueError):
            MultiHeadSelfAttention(10, 3)

    def test_split_and_merge_heads(self):
        m = MultiHeadSelfAttention(8, 2)
        x = torch.arange(2 * 3 * 8, dtype=torch.float32).view(2, 3, 8)
        s = m.split_heads(x)
        assert s.shape == (2, 2, 3, 4)
        torch.testing.assert_close(s[0, 1, 2], x[0, 2, 4:])
        torch.testing.assert_close(m.merge_heads(s), x)

    def test_matches_nn_multiheadattention(self):
        ref, mine, x = pair()
        expected, w_ref = ref(x, x, x, average_attn_weights=False)
        out, w = mine(x)
        assert out.shape == (3, 5, 8) and w.shape == (3, 2, 5, 5)
        torch.testing.assert_close(out, expected)
        torch.testing.assert_close(w, w_ref)

    def test_causal_matches_nn_multiheadattention(self):
        ref, mine, x = pair(seed=1)
        blocked = torch.ones(5, 5, dtype=torch.bool).triu(1)
        expected, _ = ref(x, x, x, attn_mask=blocked)
        out, w = mine(x, causal=True)
        torch.testing.assert_close(out, expected)
        assert torch.all(w.triu(1) == 0)

    def test_key_padding_mask_matches_nn_multiheadattention(self):
        ref, mine, x = pair(seed=2)
        pad = torch.tensor([[False] * 5, [False] * 3 + [True] * 2, [False] * 4 + [True]])
        expected, _ = ref(x, x, x, key_padding_mask=pad)
        out, w = mine(x, key_padding_mask=pad)
        torch.testing.assert_close(out, expected)
        assert torch.all(w[1, :, :, 3:] == 0)

    def test_permutation_equivariant_without_mask(self):
        _, mine, x = pair(seed=3)
        perm = torch.tensor([4, 2, 0, 3, 1])
        out, _ = mine(x)
        out_perm, _ = mine(x[:, perm])
        torch.testing.assert_close(out_perm, out[:, perm])


class TestTransformerBlock:
    def make(self):
        torch.manual_seed(0)
        block = TransformerBlock(8, 2, 32).double()
        x = torch.randn(2, 6, 8, dtype=torch.float64)
        return block, x

    def test_structure_and_shape(self):
        block, x = self.make()
        assert isinstance(block.attn, MultiHeadSelfAttention)
        assert isinstance(block.norm1, nn.LayerNorm) and isinstance(block.norm2, nn.LayerNorm)
        assert block(x).shape == x.shape

    def test_pre_norm_residual_formula(self):
        block, x = self.make()
        a, _ = block.attn(block.norm1(x))
        h = x + a
        expected = h + block.ffn(block.norm2(h))
        torch.testing.assert_close(block(x), expected)

    def test_residual_path_is_identity_when_sublayers_output_zero(self):
        block, x = self.make()
        with torch.no_grad():
            block.attn.out_proj.weight.zero_()
            block.attn.out_proj.bias.zero_()
            block.ffn[2].weight.zero_()
            block.ffn[2].bias.zero_()
        torch.testing.assert_close(block(x), x)

    def test_causal_block_does_not_see_the_future(self):
        block, x = self.make()
        x2 = x.clone()
        x2[:, 4:] = torch.randn(2, 2, 8, dtype=torch.float64)
        y, y2 = block(x, causal=True), block(x2, causal=True)
        torch.testing.assert_close(y[:, :4], y2[:, :4])
        assert not torch.allclose(block(x)[:, :4], block(x2)[:, :4])

    def test_gradients_reach_every_parameter(self):
        block, x = self.make()
        block(x, causal=True).pow(2).mean().backward()
        for name, p in block.named_parameters():
            assert p.grad is not None and p.grad.abs().sum() > 0, name
