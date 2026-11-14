"""Tests for exercises/deep_learning/tensors_basics.py (lesson: pytorch-fundamentals)."""

import numpy as np
import pytest
import torch
from deep_learning.tensors_basics import flatten_batch, one_hot, row_shares, standardise_columns, to_features

pytestmark = pytest.mark.exercise


def test_to_features_is_float32_and_works_with_linear():
    torch.manual_seed(0)
    t = to_features(np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]))
    assert t.dtype == torch.float32
    assert torch.nn.Linear(3, 1)(t).shape == (2, 1)


def test_to_features_does_not_share_memory_with_the_array():
    array = np.zeros(3)
    t = to_features(array)
    array[0] = 5.0
    torch.testing.assert_close(t, torch.zeros(3))


def test_standardise_columns_gives_zero_mean_unit_std_per_column():
    torch.manual_seed(0)
    x = torch.randn(50, 4, dtype=torch.float64) * torch.tensor([1.0, 10.0, 100.0, 0.1], dtype=torch.float64) + 7
    z = standardise_columns(x)
    assert z.shape == x.shape
    torch.testing.assert_close(z.mean(dim=0), torch.zeros(4, dtype=torch.float64), atol=1e-12, rtol=0)
    torch.testing.assert_close(z.std(dim=0, correction=0), torch.ones(4, dtype=torch.float64), atol=1e-6, rtol=0)


def test_standardise_columns_matches_numpy_and_leaves_input_alone():
    x = torch.tensor([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0], [10.0, 11.0, 12.0]], dtype=torch.float64)
    before = x.clone()
    a = x.numpy()
    expected = (a - a.mean(axis=0)) / (a.std(axis=0) + 1e-8)
    torch.testing.assert_close(standardise_columns(x), torch.from_numpy(expected))
    torch.testing.assert_close(x, before)


def test_row_shares_divides_each_row_by_its_own_sum():
    x = torch.tensor([[1.0, 1.0, 2.0], [3.0, 0.0, 1.0], [5.0, 5.0, 0.0], [2.0, 2.0, 4.0]])
    expected = torch.tensor([[0.25, 0.25, 0.5], [0.75, 0.0, 0.25], [0.5, 0.5, 0.0], [0.25, 0.25, 0.5]])
    torch.testing.assert_close(row_shares(x), expected)
    torch.testing.assert_close(row_shares(x).sum(dim=1), torch.ones(4))


def test_flatten_batch_keeps_the_batch_dimension():
    images = torch.arange(2 * 8 * 8, dtype=torch.float32).reshape(2, 8, 8)
    flat = flatten_batch(images)
    assert flat.shape == (2, 64)
    torch.testing.assert_close(flat[1], images[1].reshape(64))


def test_flatten_batch_works_on_a_non_contiguous_batch():
    images = torch.arange(3 * 4 * 5, dtype=torch.float32).reshape(3, 4, 5).transpose(1, 2)
    assert not images.is_contiguous()
    flat = flatten_batch(images)
    assert flat.shape == (3, 20)
    torch.testing.assert_close(flat[2], images[2].reshape(20))


def test_one_hot_shape_dtype_and_values():
    encoded = one_hot(torch.tensor([2, 0, 1, 2]), num_classes=3)
    assert encoded.dtype == torch.float32
    expected = torch.tensor([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    torch.testing.assert_close(encoded, expected)
    assert one_hot(torch.tensor([0, 1]), num_classes=5).shape == (2, 5)
