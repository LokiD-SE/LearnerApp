"""Sinusoidal positional encoding (Vaswani et al. 2017, section 3.5) - lesson attention-and-transformers."""

import math  # noqa: F401 - you will need it

import torch


def sinusoidal_encoding(n_positions, d_model, dtype=torch.float32):
    """Return the (n_positions, d_model) table PE with

    PE[pos, 2i]   = sin(pos / 10000 ** (2i / d_model))
    PE[pos, 2i+1] = cos(pos / 10000 ** (2i / d_model))

    d_model must be even (raise ValueError otherwise).
    """
    # First draft - the right shape, the wrong numbers, and no check on d_model.
    pos = torch.arange(n_positions, dtype=torch.float64)[:, None]
    i = torch.arange(d_model // 2, dtype=torch.float64)
    angles = pos / (10000 ** (i / d_model))
    pe = torch.zeros(n_positions, d_model, dtype=torch.float64)
    pe[:, 0::2] = torch.cos(angles)
    pe[:, 1::2] = torch.sin(angles)
    return pe.to(dtype)


def shift_matrix(k, d_model, dtype=torch.float64):
    """Return the (d_model, d_model) matrix R with PE[pos + k] == PE[pos] @ R for every pos.

    It is block-diagonal: for each pair of columns (2i, 2i+1) with frequency w = 1 / 10000 ** (2i / d_model)
    the 2x2 block is [[cos(w k), -sin(w k)], [sin(w k), cos(w k)]]. This is the "linear function of PE[pos]"
    from section 3.5 of the paper. d_model must be even (raise ValueError otherwise).
    """
    raise NotImplementedError("shift_matrix")
