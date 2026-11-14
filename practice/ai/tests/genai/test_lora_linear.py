"""Checks exercises/genai/lora_linear.py - lesson fine-tuning-vs-rag-vs-prompting."""

import pytest
import torch
import torch.nn.functional as F
from genai.lora_linear import LoRALinear, add_lora, count_parameters
from torch import nn

pytestmark = pytest.mark.exercise


def base_layer(seed=0, d_in=6, d_out=4):
    torch.manual_seed(seed)
    return nn.Linear(d_in, d_out).double()


class TestLoRALinear:
    def test_shapes_and_frozen_base(self):
        layer = LoRALinear(base_layer(), r=2)
        assert layer.lora_A.shape == (2, 6) and layer.lora_B.shape == (4, 2)
        assert not any(p.requires_grad for p in layer.base.parameters())
        assert layer.lora_A.requires_grad and layer.lora_B.requires_grad

    def test_starts_exactly_at_the_base_model(self):
        base = base_layer()
        layer = LoRALinear(base, r=3)
        assert torch.count_nonzero(layer.lora_B) == 0
        assert torch.count_nonzero(layer.lora_A) > 0
        x = torch.randn(5, 6, dtype=torch.float64)
        torch.testing.assert_close(layer(x), base(x))

    def test_rejects_bad_rank(self):
        for r in (0, 5):
            with pytest.raises(ValueError):
                LoRALinear(base_layer(), r=r)

    def test_scaling_is_alpha_over_r(self):
        assert LoRALinear(base_layer(), r=2).scaling == pytest.approx(1.0)
        assert LoRALinear(base_layer(), r=2, alpha=8).scaling == pytest.approx(4.0)

    def test_forward_is_base_plus_scaled_low_rank_update(self):
        layer = LoRALinear(base_layer(), r=2, alpha=6)
        with torch.no_grad():
            layer.lora_B.copy_(torch.arange(8, dtype=torch.float64).view(4, 2) / 10)
        x = torch.randn(3, 6, dtype=torch.float64)
        expected = layer.base(x) + 3.0 * x @ (layer.lora_B @ layer.lora_A).T
        torch.testing.assert_close(layer(x), expected)
        torch.testing.assert_close(layer.delta_weight(), 3.0 * layer.lora_B @ layer.lora_A)
        assert torch.linalg.matrix_rank(layer.delta_weight()) <= 2

    def test_disabled_adapter_is_the_base(self):
        layer = LoRALinear(base_layer(), r=2)
        with torch.no_grad():
            layer.lora_B.fill_(0.5)
        x = torch.randn(3, 6, dtype=torch.float64)
        layer.enabled = False
        torch.testing.assert_close(layer(x), layer.base(x))

    def test_training_changes_only_the_adapter(self):
        base = base_layer(1)
        w0, b0 = base.weight.detach().clone(), base.bias.detach().clone()
        layer = LoRALinear(base, r=2)
        opt = torch.optim.SGD([p for p in layer.parameters() if p.requires_grad], lr=0.1)
        x, y = torch.randn(16, 6, dtype=torch.float64), torch.randn(16, 4, dtype=torch.float64)
        for _ in range(3):
            opt.zero_grad()
            F.mse_loss(layer(x), y).backward()
            opt.step()
        assert torch.equal(layer.base.weight, w0) and torch.equal(layer.base.bias, b0)
        assert torch.count_nonzero(layer.lora_B) > 0

    def test_merged_matches_and_leaves_base_alone(self):
        layer = LoRALinear(base_layer(2), r=2, alpha=4)
        with torch.no_grad():
            layer.lora_B.normal_()
        w0 = layer.base.weight.detach().clone()
        merged = layer.merged()
        assert type(merged) is nn.Linear
        x = torch.randn(4, 6, dtype=torch.float64)
        torch.testing.assert_close(merged(x), layer(x))
        assert torch.equal(layer.base.weight, w0)


class TestCountingAndAdding:
    def model(self):
        torch.manual_seed(0)
        return nn.Sequential(nn.Linear(8, 64), nn.ReLU(), nn.Linear(64, 64), nn.ReLU(), nn.Linear(64, 2))

    def test_count_parameters(self):
        m = self.model()
        assert count_parameters(m) == (4866, 4866)
        m[0].weight.requires_grad_(False)
        assert count_parameters(m) == (4866 - 512, 4866)

    def test_add_lora_freezes_everything_else(self):
        m = add_lora(self.model(), ["0", "2", "4"], r=2)
        assert all(isinstance(m[i], LoRALinear) for i in (0, 2, 4))
        # r * (in + out) per adapted layer; base weights and biases stay in the total
        assert count_parameters(m) == (2 * (8 + 64) + 2 * (64 + 64) + 2 * (64 + 2), 4866 + 532)

    def test_add_lora_starts_at_base_output(self):
        m = self.model()
        x = torch.randn(5, 8)
        before = m(x).detach()
        add_lora(m, ["2"], r=1)
        torch.testing.assert_close(m(x), before)
        assert count_parameters(m)[0] == 1 * (64 + 64)

    def test_add_lora_nested_names(self):
        outer = nn.Sequential()
        outer.add_module("block", nn.Sequential(nn.Linear(4, 4)))
        add_lora(outer, ["block.0"], r=1)
        assert isinstance(outer.block[0], LoRALinear)

    def test_add_lora_rejects_bad_targets(self):
        with pytest.raises(KeyError):
            add_lora(self.model(), ["9"])
        with pytest.raises(TypeError):
            add_lora(self.model(), ["1"])
