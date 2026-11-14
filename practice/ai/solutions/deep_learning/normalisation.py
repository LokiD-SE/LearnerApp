"""Initialisation scales, batch norm, layer norm and inverted dropout by hand (lesson: training-deep-networks).

Each function mirrors a PyTorch 2.15 layer or initialiser so the tests can compare your numbers with
``nn.BatchNorm1d``, ``nn.LayerNorm`` and ``nn.init``.
"""

import math

import torch


def xavier_uniform_bound(fan_in, fan_out, gain=1.0):
    """Bound ``a`` of Glorot/Xavier uniform initialisation: weights are drawn from U(-a, a) with
    ``a = gain * sqrt(6 / (fan_in + fan_out))`` (as in ``nn.init.xavier_uniform_``)."""
    return gain * math.sqrt(6.0 / (fan_in + fan_out))


def he_normal_std(fan_in):
    """Standard deviation of He (Kaiming) normal initialisation for ReLU layers, ``sqrt(2 / fan_in)``
    (``nn.init.kaiming_normal_`` with ``mode='fan_in'``, ``nonlinearity='relu'``)."""
    return math.sqrt(2.0 / fan_in)


def batch_norm_train(x, gamma, beta, running_mean, running_var, momentum=0.1, eps=1e-5):
    """Batch norm forward pass in training mode, for ``x`` of shape (batch, features).

    Normalise each feature with the batch mean and the *biased* batch variance, then scale by ``gamma`` and
    shift by ``beta``. Update ``running_mean`` and ``running_var`` in place with
    ``running = (1 - momentum) * running + momentum * batch_stat``, using the *unbiased* batch variance for
    ``running_var`` - exactly what ``nn.BatchNorm1d`` does. Raise ``ValueError`` for a batch of one row.
    """
    if x.shape[0] < 2:
        raise ValueError("batch norm in training mode needs more than one row per batch")
    mean = x.mean(dim=0)
    var = x.var(dim=0, unbiased=False)
    with torch.no_grad():
        running_mean.mul_(1 - momentum).add_(momentum * mean)
        running_var.mul_(1 - momentum).add_(momentum * x.var(dim=0, unbiased=True))
    return gamma * (x - mean) / torch.sqrt(var + eps) + beta


def batch_norm_eval(x, gamma, beta, running_mean, running_var, eps=1e-5):
    """Batch norm in evaluation mode: normalise with the running statistics, never with the batch's own."""
    return gamma * (x - running_mean) / torch.sqrt(running_var + eps) + beta


def layer_norm(x, gamma, beta, eps=1e-5):
    """Layer norm over the last dimension: each row is normalised with its own mean and biased variance,
    then scaled and shifted per feature. The same computation in training and evaluation."""
    mean = x.mean(dim=-1, keepdim=True)
    var = x.var(dim=-1, unbiased=False, keepdim=True)
    return gamma * (x - mean) / torch.sqrt(var + eps) + beta


def inverted_dropout(x, p, training, generator=None):
    """Dropout as PyTorch defines it: ``p`` is the probability of *dropping* an element.

    In training, zero each element with probability ``p`` and scale the survivors by ``1 / (1 - p)`` so the
    expected value is unchanged; with ``p == 1`` return zeros. In evaluation (``training=False``) return
    ``x`` unchanged. Draw the mask with ``torch.rand(x.shape, generator=generator)``.
    """
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"p must be between 0 and 1, got {p}")
    if not training or p == 0.0:
        return x
    if p == 1.0:
        return torch.zeros_like(x)
    keep = torch.rand(x.shape, generator=generator, dtype=x.dtype) >= p
    return x * keep / (1.0 - p)
