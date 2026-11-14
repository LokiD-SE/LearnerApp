"""Tests for exercises/deep_learning/autograd_steps.py (lesson: pytorch-fundamentals)."""

import pytest
import torch
from deep_learning.autograd_steps import accumulated_gradient, fit_line, gradient_at

pytestmark = pytest.mark.exercise


def test_gradient_at_matches_the_hand_derivative():
    w = torch.tensor([2.0, -1.0])
    x = torch.tensor([3.0, 4.0])
    grad = gradient_at(lambda v: ((v * x).sum() - 1.0) ** 2, w)
    torch.testing.assert_close(grad, torch.tensor([6.0, 8.0]))
    assert not grad.requires_grad


def test_gradient_at_matches_finite_differences_in_float64():
    torch.manual_seed(0)
    x = torch.randn(5, dtype=torch.float64)

    def fn(v):
        return torch.tanh(v).pow(2).sum() + (v[0] * v[1]).exp()

    grad = gradient_at(fn, x)
    eps = 1e-6
    numeric = torch.stack([(fn(x + eps * e) - fn(x - eps * e)) / (2 * eps) for e in torch.eye(5, dtype=torch.float64)])
    torch.testing.assert_close(grad, numeric, rtol=1e-6, atol=1e-8)


def test_gradient_at_leaves_the_input_untouched():
    x = torch.tensor([1.0, 2.0], requires_grad=True)
    gradient_at(lambda v: (v**2).sum(), x)
    gradient_at(lambda v: (v**2).sum(), x)
    assert x.grad is None
    assert x.requires_grad
    plain = torch.tensor([1.0, 2.0])
    torch.testing.assert_close(gradient_at(lambda v: (v**3).sum(), plain), torch.tensor([3.0, 12.0]))
    assert not plain.requires_grad


def test_fit_line_recovers_the_true_line():
    xs = torch.linspace(-1, 1, 8, dtype=torch.float64)
    ys = 3 * xs + 0.5
    w, b, losses = fit_line(xs, ys, learning_rate=0.5, steps=100)
    assert w == pytest.approx(3.0, abs=1e-4)
    assert b == pytest.approx(0.5, abs=1e-4)
    assert len(losses) == 100
    assert all(isinstance(v, float) for v in losses)


def test_fit_line_losses_fall_every_step_like_the_lesson():
    xs = torch.linspace(-1, 1, 8)
    ys = 3 * xs + 0.5
    _, _, losses = fit_line(xs, ys, learning_rate=0.5, steps=4)
    assert losses == pytest.approx([4.1071, 1.2595, 0.4113, 0.1343], abs=1e-4)
    assert all(later < earlier for earlier, later in zip(losses, losses[1:]))


def _sum_squared(w, xb, yb):
    return ((xb @ w - yb) ** 2).sum()


def test_accumulated_gradient_equals_the_full_batch_gradient():
    torch.manual_seed(0)
    X = torch.randn(10, 3, dtype=torch.float64)
    y = torch.randn(10, dtype=torch.float64)
    w = torch.randn(3, dtype=torch.float64, requires_grad=True)
    batches = [(X[:4], y[:4]), (X[4:7], y[4:7]), (X[7:], y[7:])]
    expected = torch.autograd.grad(((X @ w - y) ** 2).mean(), w)[0]
    got = accumulated_gradient(w, batches, _sum_squared)
    torch.testing.assert_close(got, expected)


def test_accumulated_gradient_handles_unequal_batches_and_resets_grad():
    torch.manual_seed(1)
    X = torch.randn(7, 2, dtype=torch.float64)
    y = torch.randn(7, dtype=torch.float64)
    w = torch.randn(2, dtype=torch.float64, requires_grad=True)
    batches = [(X[:6], y[:6]), (X[6:], y[6:])]
    expected = torch.autograd.grad(((X @ w - y) ** 2).mean(), w)[0]
    torch.testing.assert_close(accumulated_gradient(w, batches, _sum_squared), expected)
    assert w.grad is None
    torch.testing.assert_close(accumulated_gradient(w, batches, _sum_squared), expected)
