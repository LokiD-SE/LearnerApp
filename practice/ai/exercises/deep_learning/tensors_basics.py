"""Tensor basics - exercise. Reference solution: solutions/deep_learning/tensors_basics.py.

Lesson: PyTorch fundamentals (#/lesson/pytorch-fundamentals).
Some functions are a colleague's first drafts - they run, but the tests show where they go wrong.
Run: .venv/bin/python -m pytest tests/deep_learning/test_tensors_basics.py
"""

import numpy as np
import torch


def to_features(array: np.ndarray) -> torch.Tensor:
    """Return a float32 tensor with the values of ``array`` that does NOT share memory with it.

    NumPy arrays are float64 by default, but nn.Linear's weights are float32, so features must be converted.
    Later changes to ``array`` must not change the tensor.
    """
    # First draft: fast, no copy. Two problems - which?
    return torch.from_numpy(array)


def standardise_columns(x: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
    """Return (x - column mean) / (column standard deviation + eps) for a 2-D tensor (rows = examples).

    Use the population standard deviation (correction=0), like scikit-learn's StandardScaler.
    The input tensor must not be modified.
    """
    raise NotImplementedError


def row_shares(x: torch.Tensor) -> torch.Tensor:
    """Return each row of a 2-D tensor divided by that row's sum, so every row sums to 1.

    Example: a merchant's spend per category divided by the merchant's total spend.
    """
    # First draft. It even runs on some shapes - check what it divides by.
    return x / x.sum(dim=1)


def flatten_batch(images: torch.Tensor) -> torch.Tensor:
    """Turn a batch of shape (N, H, W) into (N, H*W), keeping the batch dimension.

    Must work for non-contiguous input too (for example a transposed batch).
    """
    # First draft.
    return images.view(images.shape[0], -1)


def one_hot(labels: torch.Tensor, num_classes: int) -> torch.Tensor:
    """Return a float32 tensor of shape (N, num_classes) with a 1.0 in each row at the label's index."""
    raise NotImplementedError
