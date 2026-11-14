"""Tests for exercises/deep_learning/normalisation.py (lesson: training-deep-networks)."""

import math

import pytest
import torch
from deep_learning.normalisation import (
    batch_norm_eval,
    batch_norm_train,
    he_normal_std,
    inverted_dropout,
    layer_norm,
    xavier_uniform_bound,
)
from torch import nn

pytestmark = pytest.mark.exercise


def test_xavier_bound_matches_the_formula_and_torch():
    assert xavier_uniform_bound(256, 256) == pytest.approx(math.sqrt(6 / 512))
    assert xavier_uniform_bound(20, 64, gain=5 / 3) == pytest.approx(5 / 3 * math.sqrt(6 / 84))
    torch.manual_seed(0)
    w = torch.empty(300, 200)
    nn.init.xavier_uniform_(w)
    assert w.abs().max().item() <= xavier_uniform_bound(200, 300)
    assert w.abs().max().item() > 0.99 * xavier_uniform_bound(200, 300)


def test_he_std_matches_kaiming_normal():
    assert he_normal_std(256) == pytest.approx(math.sqrt(2 / 256))
    torch.manual_seed(0)
    w = torch.empty(400, 256)
    nn.init.kaiming_normal_(w, nonlinearity="relu")
    assert w.std().item() == pytest.approx(he_normal_std(256), rel=0.02)


def make_batches(seed=0):
    g = torch.Generator().manual_seed(seed)
    scale = torch.tensor([1.0, 10.0, 0.1], dtype=torch.float64)
    shift = torch.tensor([5.0, -3.0, 0.0], dtype=torch.float64)
    return [torch.randn(8, 3, generator=g, dtype=torch.float64) * scale + shift for _ in range(4)]


def test_batch_norm_train_matches_batchnorm1d_and_updates_running_stats():
    torch.manual_seed(0)
    bn = nn.BatchNorm1d(3).double()
    with torch.no_grad():
        bn.weight.copy_(torch.tensor([1.5, 0.5, 2.0]))
        bn.bias.copy_(torch.tensor([0.1, -0.2, 0.3]))
    gamma, beta = bn.weight.detach().clone(), bn.bias.detach().clone()
    running_mean = torch.zeros(3, dtype=torch.float64)
    running_var = torch.ones(3, dtype=torch.float64)
    bn.train()
    for xb in make_batches():
        ours = batch_norm_train(xb, gamma, beta, running_mean, running_var)
        torch.testing.assert_close(ours, bn(xb).detach())
    torch.testing.assert_close(running_mean, bn.running_mean)
    torch.testing.assert_close(running_var, bn.running_var)


def test_batch_norm_eval_uses_running_stats():
    torch.manual_seed(0)
    bn = nn.BatchNorm1d(3).double()
    batches = make_batches()
    for xb in batches:
        bn(xb)
    bn.eval()
    gamma, beta = bn.weight.detach(), bn.bias.detach()
    x = batches[0][:1]
    torch.testing.assert_close(batch_norm_eval(x, gamma, beta, bn.running_mean, bn.running_var), bn(x).detach())


def test_batch_norm_train_rejects_a_single_row():
    with pytest.raises(ValueError):
        batch_norm_train(torch.ones(1, 3), torch.ones(3), torch.zeros(3), torch.zeros(3), torch.ones(3))


def test_layer_norm_matches_torch():
    torch.manual_seed(0)
    ln = nn.LayerNorm(5).double()
    with torch.no_grad():
        ln.weight.copy_(torch.linspace(0.5, 1.5, 5))
        ln.bias.copy_(torch.linspace(-0.2, 0.2, 5))
    x = torch.randn(4, 5, dtype=torch.float64) * 3 + 1
    torch.testing.assert_close(layer_norm(x, ln.weight.detach(), ln.bias.detach()), ln(x).detach())
    # One row alone gives the same result as inside the batch: layer norm does not depend on the batch.
    torch.testing.assert_close(layer_norm(x[:1], ln.weight.detach(), ln.bias.detach()), ln(x).detach()[:1])


def test_dropout_zeroes_with_probability_p_and_rescales():
    g = torch.Generator().manual_seed(0)
    x = torch.ones(20000, dtype=torch.float64)
    out = inverted_dropout(x, 0.3, training=True, generator=g)
    kept = out[out != 0]
    torch.testing.assert_close(kept, torch.full_like(kept, 1 / 0.7))
    assert (out == 0).double().mean().item() == pytest.approx(0.3, abs=0.02)
    assert out.mean().item() == pytest.approx(1.0, abs=0.03)


def test_dropout_eval_and_edge_cases():
    x = torch.arange(6, dtype=torch.float64)
    torch.testing.assert_close(inverted_dropout(x, 0.5, training=False), x)
    torch.testing.assert_close(inverted_dropout(x, 0.0, training=True), x)
    torch.testing.assert_close(inverted_dropout(x, 1.0, training=True), torch.zeros(6, dtype=torch.float64))
    with pytest.raises(ValueError):
        inverted_dropout(x, 1.5, training=True)
