"""Autograd by hand - reference solution. Exercise: exercises/deep_learning/autograd_steps.py.

Lesson: PyTorch fundamentals (#/lesson/pytorch-fundamentals).
"""

from collections.abc import Callable, Sequence

import torch


def gradient_at(fn: Callable[[torch.Tensor], torch.Tensor], x: torch.Tensor) -> torch.Tensor:
    """Return d fn(x) / dx for a function that returns a scalar tensor.

    ``x`` itself must not be changed: its ``requires_grad`` and ``grad`` stay as they were.
    The result does not require grad.
    """
    leaf = x.detach().clone().requires_grad_(True)
    (grad,) = torch.autograd.grad(fn(leaf), leaf)
    return grad


def fit_line(
    xs: torch.Tensor, ys: torch.Tensor, learning_rate: float = 0.5, steps: int = 100
) -> tuple[float, float, list[float]]:
    """Fit y = w*x + b by gradient descent on the mean squared error, with autograd computing the gradients.

    Start from w = b = 0. Return (w, b, losses), where losses[i] is the loss computed at step i
    (before that step's update) as a Python float.
    """
    w = torch.zeros(1, dtype=xs.dtype, requires_grad=True)
    b = torch.zeros(1, dtype=xs.dtype, requires_grad=True)
    losses = []
    for _ in range(steps):
        loss = ((w * xs + b - ys) ** 2).mean()
        loss.backward()
        with torch.no_grad():
            w -= learning_rate * w.grad
            b -= learning_rate * b.grad
        w.grad = None
        b.grad = None
        losses.append(loss.item())
    return w.item(), b.item(), losses


def accumulated_gradient(
    w: torch.Tensor,
    batches: Sequence[tuple[torch.Tensor, torch.Tensor]],
    loss_fn: Callable[[torch.Tensor, torch.Tensor, torch.Tensor], torch.Tensor],
) -> torch.Tensor:
    """Gradient accumulation: return the gradient of the MEAN loss over all examples, using one backward per batch.

    ``w`` is a leaf tensor with requires_grad=True and ``w.grad`` is None on entry. ``loss_fn(w, xb, yb)``
    returns the SUM of the per-example losses of one batch. Batches may have different sizes.
    Return a detached copy of ``w.grad`` and leave ``w.grad`` as None afterwards.
    """
    n = sum(len(yb) for _, yb in batches)
    for xb, yb in batches:
        (loss_fn(w, xb, yb) / n).backward()
    grad = w.grad.detach().clone()
    w.grad = None
    return grad
