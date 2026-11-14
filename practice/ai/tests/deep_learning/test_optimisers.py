"""Tests for exercises/deep_learning/optimisers.py (lesson: training-deep-networks)."""

import pytest
import torch
from deep_learning.optimisers import adamw_step, sgd_momentum_step, warmup_cosine_lr
from torch.optim.lr_scheduler import CosineAnnealingLR, LinearLR, SequentialLR

pytestmark = pytest.mark.exercise


def gradient_sequence(steps, shapes, seed=0):
    g = torch.Generator().manual_seed(seed)
    return [[torch.randn(s, generator=g, dtype=torch.float64) for s in shapes] for _ in range(steps)]


@pytest.mark.parametrize("weight_decay", [0.0, 0.01])
def test_sgd_momentum_matches_torch(weight_decay):
    torch.manual_seed(0)
    shapes = [(3, 4), (4,)]
    start = [torch.randn(s, dtype=torch.float64) for s in shapes]
    ours = [p.clone() for p in start]
    theirs = [p.clone().requires_grad_(True) for p in start]
    opt = torch.optim.SGD(theirs, lr=0.05, momentum=0.9, weight_decay=weight_decay)
    buffers = [None, None]
    for grads in gradient_sequence(6, shapes):
        buffers = sgd_momentum_step(ours, grads, buffers, lr=0.05, momentum=0.9, weight_decay=weight_decay)
        for p, grad in zip(theirs, grads):
            p.grad = grad.clone()
        opt.step()
    for a, b in zip(ours, theirs):
        torch.testing.assert_close(a, b.detach())


def test_sgd_first_step_uses_the_gradient_as_the_buffer():
    p = [torch.tensor([1.0, 2.0], dtype=torch.float64)]
    buffers = sgd_momentum_step(p, [torch.tensor([0.5, -1.0], dtype=torch.float64)], [None], lr=0.1, momentum=0.9)
    torch.testing.assert_close(buffers[0], torch.tensor([0.5, -1.0], dtype=torch.float64))
    torch.testing.assert_close(p[0], torch.tensor([0.95, 2.1], dtype=torch.float64))


@pytest.mark.parametrize("weight_decay", [0.0, 0.1])
def test_adamw_matches_torch(weight_decay):
    torch.manual_seed(1)
    start = torch.randn(5, dtype=torch.float64)
    ours = start.clone()
    theirs = start.clone().requires_grad_(True)
    opt = torch.optim.AdamW([theirs], lr=0.01, betas=(0.9, 0.999), eps=1e-8, weight_decay=weight_decay)
    state = {}
    for (grad,) in gradient_sequence(8, [(5,)], seed=2):
        state = adamw_step(ours, grad, state, lr=0.01, weight_decay=weight_decay)
        theirs.grad = grad.clone()
        opt.step()
    assert state["step"] == 8
    torch.testing.assert_close(ours, theirs.detach())


def test_adamw_decays_a_weight_with_no_gradient():
    """Decoupled decay shrinks an unused weight by (1 - lr * wd) per step; Adam's L2 version does not."""
    w = torch.tensor([1.0], dtype=torch.float64)
    state = {}
    for _ in range(200):
        state = adamw_step(w, torch.zeros(1, dtype=torch.float64), state, lr=0.01, weight_decay=0.1)
    assert w.item() == pytest.approx(0.999**200, rel=1e-9)


def test_warmup_cosine_matches_torch_schedulers():
    w = torch.zeros(1, requires_grad=True)
    opt = torch.optim.AdamW([w], lr=0.001)
    warmup = LinearLR(opt, start_factor=0.1, end_factor=1.0, total_iters=5)
    cosine = CosineAnnealingLR(opt, T_max=15, eta_min=0.00001)
    sched = SequentialLR(opt, schedulers=[warmup, cosine], milestones=[5])
    expected = []
    for _ in range(20):
        expected.append(opt.param_groups[0]["lr"])
        opt.step()
        sched.step()
    ours = [warmup_cosine_lr(s, 0.001, 5, 20, start_factor=0.1, eta_min=0.00001) for s in range(20)]
    assert ours == pytest.approx(expected, rel=1e-9, abs=1e-12)


def test_warmup_cosine_shape():
    lrs = [warmup_cosine_lr(s, 1.0, 10, 110) for s in range(110)]
    assert lrs[0] == pytest.approx(0.1)
    assert lrs[10] == pytest.approx(1.0)
    assert all(a < b for a, b in zip(lrs[:10], lrs[1:11]))
    assert all(a >= b for a, b in zip(lrs[10:], lrs[11:]))
    assert lrs[60] == pytest.approx(0.5)
    with pytest.raises(ValueError):
        warmup_cosine_lr(0, 1.0, 0, 10)
