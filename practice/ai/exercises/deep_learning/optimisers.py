"""Optimiser steps and a learning-rate schedule written by hand (lesson: training-deep-networks).

Each function must give the same numbers as PyTorch 2.15's own implementation, so you can see exactly what
``torch.optim.SGD(momentum=...)``, ``torch.optim.AdamW`` and a warmup-plus-cosine schedule do.
"""

import math  # noqa: F401 - you will need it

import torch


@torch.no_grad()
def sgd_momentum_step(params, grads, buffers, lr, momentum, weight_decay=0.0):
    """Update ``params`` in place the way ``torch.optim.SGD(lr, momentum, weight_decay)`` does.

    PyTorch's form (see the note in the ``torch.optim.SGD`` docstring)::

        g = grad + weight_decay * p            # L2 penalty folded into the gradient
        v = g                     on the first step (buffer is None)
        v = momentum * v + g      afterwards
        p = p - lr * v

    ``params`` and ``grads`` are lists of tensors of matching shapes; ``buffers`` is a list of the same length
    holding ``None`` before the first step. Return the list of updated buffers.
    """
    raise NotImplementedError


@torch.no_grad()
def adamw_step(param, grad, state, lr=1e-3, betas=(0.9, 0.999), eps=1e-8, weight_decay=1e-2):
    """Update ``param`` in place the way ``torch.optim.AdamW`` does (Loshchilov and Hutter, Algorithm 2).

    ``state`` is a dict that starts empty and keeps ``step`` (int), ``m`` and ``v`` (tensors like ``param``)::

        p = p - lr * weight_decay * p          # decoupled decay: not part of the gradient
        m = beta1 * m + (1 - beta1) * g
        v = beta2 * v + (1 - beta2) * g * g
        m_hat = m / (1 - beta1 ** t);  v_hat = v / (1 - beta2 ** t)
        p = p - lr * m_hat / (sqrt(v_hat) + eps)
    """
    # Starting draft: this is Adam with an L2 penalty (weight decay added to the gradient), not AdamW.
    beta1, beta2 = betas
    if not state:
        state["step"] = 0
        state["m"] = torch.zeros_like(param)
        state["v"] = torch.zeros_like(param)
    state["step"] += 1
    t = state["step"]
    grad = grad + weight_decay * param
    state["m"] = beta1 * state["m"] + (1 - beta1) * grad
    state["v"] = beta2 * state["v"] + (1 - beta2) * grad * grad
    m_hat = state["m"] / (1 - beta1**t)
    v_hat = state["v"] / (1 - beta2**t)
    param -= lr * m_hat / (v_hat.sqrt() + eps)
    return state


def warmup_cosine_lr(step, base_lr, warmup_steps, total_steps, start_factor=0.1, eta_min=0.0):
    """Learning rate used at ``step`` (0-based) by linear warmup then cosine decay.

    Matches ``SequentialLR([LinearLR(start_factor, 1.0, total_iters=warmup_steps),
    CosineAnnealingLR(T_max=total_steps - warmup_steps, eta_min)], milestones=[warmup_steps])``:

    - for ``step < warmup_steps``: ``base_lr * (start_factor + (1 - start_factor) * step / warmup_steps)``
    - afterwards, with ``t = step - warmup_steps`` and ``T = total_steps - warmup_steps``:
      ``eta_min + (base_lr - eta_min) * (1 + cos(pi * t / T)) / 2``
    """
    raise NotImplementedError
