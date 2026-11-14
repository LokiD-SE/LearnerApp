"""Initialisation scales, batch norm, layer norm and inverted dropout by hand (lesson: training-deep-networks).

Each function mirrors a PyTorch 2.15 layer or initialiser so the tests can compare your numbers with
``nn.BatchNorm1d``, ``nn.LayerNorm`` and ``nn.init``.
"""

import math  # noqa: F401 - you will need it

import torch


def xavier_uniform_bound(fan_in, fan_out, gain=1.0):
    """Bound ``a`` of Glorot/Xavier uniform initialisation: weights are drawn from U(-a, a) with
    ``a = gain * sqrt(6 / (fan_in + fan_out))`` (as in ``nn.init.xavier_uniform_``)."""
    raise NotImplementedError


def he_normal_std(fan_in):
    """Standard deviation of He (Kaiming) normal initialisation for ReLU layers, ``sqrt(2 / fan_in)``
    (``nn.init.kaiming_normal_`` with ``mode='fan_in'``, ``nonlinearity='relu'``)."""
    raise NotImplementedError


def batch_norm_train(x, gamma, beta, running_mean, running_var, momentum=0.1, eps=1e-5):
    """Batch norm forward pass in training mode, for ``x`` of shape (batch, features).

    Normalise each feature with the batch mean and the *biased* batch variance, then scale by ``gamma`` and
    shift by ``beta``. Update ``running_mean`` and ``running_var`` in place with
    ``running = (1 - momentum) * running + momentum * batch_stat``, using the *unbiased* batch variance for
    ``running_var`` - exactly what ``nn.BatchNorm1d`` does. Raise ``ValueError`` for a batch of one row.
    """
    # Starting draft: normalises over the wrong dimension and never updates the running statistics.
    mean = x.mean(dim=1, keepdim=True)
    var = x.var(dim=1, keepdim=True)
    return gamma * (x - mean) / torch.sqrt(var + eps) + beta


def batch_norm_eval(x, gamma, beta, running_mean, running_var, eps=1e-5):
    """Batch norm in evaluation mode: normalise with the running statistics, never with the batch's own."""
    raise NotImplementedError


def layer_norm(x, gamma, beta, eps=1e-5):
    """Layer norm over the last dimension: each row is normalised with its own mean and biased variance,
    then scaled and shifted per feature. The same computation in training and evaluation."""
    raise NotImplementedError


def inverted_dropout(x, p, training, generator=None):
    """Dropout as PyTorch defines it: ``p`` is the probability of *dropping* an element.

    In training, zero each element with probability ``p`` and scale the survivors by ``1 / (1 - p)`` so the
    expected value is unchanged; with ``p == 1`` return zeros. In evaluation (``training=False``) return
    ``x`` unchanged. Draw the mask with ``torch.rand(x.shape, generator=generator)``.
    """
    # Starting draft: keeps elements with probability p (the 2014 paper's meaning) and never rescales.
    keep = torch.rand(x.shape, generator=generator, dtype=x.dtype) < p
    return x * keep
