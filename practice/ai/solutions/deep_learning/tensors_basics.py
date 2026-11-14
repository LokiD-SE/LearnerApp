"""Tensor basics - reference solution. Exercise: exercises/deep_learning/tensors_basics.py.

Lesson: PyTorch fundamentals (#/lesson/pytorch-fundamentals).
"""

import numpy as np
import torch


def to_features(array: np.ndarray) -> torch.Tensor:
    """Return a float32 tensor with the values of ``array`` that does NOT share memory with it.

    NumPy arrays are float64 by default, but nn.Linear's weights are float32, so features must be converted.
    Later changes to ``array`` must not change the tensor.
    """
    return torch.tensor(array, dtype=torch.float32)


def standardise_columns(x: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
    """Return (x - column mean) / (column standard deviation + eps) for a 2-D tensor (rows = examples).

    Use the population standard deviation (correction=0), like scikit-learn's StandardScaler.
    The input tensor must not be modified.
    """
    mean = x.mean(dim=0, keepdim=True)
    std = x.std(dim=0, correction=0, keepdim=True)
    return (x - mean) / (std + eps)


def row_shares(x: torch.Tensor) -> torch.Tensor:
    """Return each row of a 2-D tensor divided by that row's sum, so every row sums to 1.

    Example: a merchant's spend per category divided by the merchant's total spend.
    """
    return x / x.sum(dim=1, keepdim=True)


def flatten_batch(images: torch.Tensor) -> torch.Tensor:
    """Turn a batch of shape (N, H, W) into (N, H*W), keeping the batch dimension.

    Must work for non-contiguous input too (for example a transposed batch).
    """
    return images.reshape(images.shape[0], -1)


def one_hot(labels: torch.Tensor, num_classes: int) -> torch.Tensor:
    """Return a float32 tensor of shape (N, num_classes) with a 1.0 in each row at the label's index."""
    return torch.nn.functional.one_hot(labels.long(), num_classes=num_classes).to(torch.float32)
