"""Checks exercises/deep_learning/positional.py - lesson attention-and-transformers."""

import math

import pytest
import torch
from deep_learning.positional import shift_matrix, sinusoidal_encoding

pytestmark = pytest.mark.exercise


class TestSinusoidalEncoding:
    def test_shape_and_dtype(self):
        pe = sinusoidal_encoding(50, 16)
        assert pe.shape == (50, 16) and pe.dtype == torch.float32
        assert sinusoidal_encoding(3, 4, dtype=torch.float64).dtype == torch.float64

    def test_position_zero_alternates_zero_and_one(self):
        pe = sinusoidal_encoding(1, 8, dtype=torch.float64)
        torch.testing.assert_close(pe[0], torch.tensor([0.0, 1, 0, 1, 0, 1, 0, 1], dtype=torch.float64))

    def test_values_follow_the_formula(self):
        d = 8
        pe = sinusoidal_encoding(10, d, dtype=torch.float64)
        for pos in (1, 2, 7):
            for i in range(d // 2):
                angle = pos / 10000 ** (2 * i / d)
                assert pe[pos, 2 * i].item() == pytest.approx(math.sin(angle))
                assert pe[pos, 2 * i + 1].item() == pytest.approx(math.cos(angle))

    def test_first_pair_is_fastest(self):
        pe = sinusoidal_encoding(2, 8, dtype=torch.float64)
        assert pe[1, 0].item() == pytest.approx(0.841471, abs=1e-6)
        assert pe[1, 6].item() == pytest.approx(0.001, abs=1e-6)

    def test_bounded_and_rows_distinct(self):
        pe = sinusoidal_encoding(200, 32, dtype=torch.float64)
        assert pe.abs().max() <= 1.0
        assert torch.cdist(pe, pe).add(torch.eye(200, dtype=torch.float64)).min() > 0.1

    def test_odd_dimension_rejected(self):
        with pytest.raises(ValueError):
            sinusoidal_encoding(4, 7)


class TestShiftMatrix:
    def test_shift_is_linear_in_pe(self):
        d, k = 16, 5
        pe = sinusoidal_encoding(60, d, dtype=torch.float64)
        r = shift_matrix(k, d)
        torch.testing.assert_close(pe[:-k] @ r, pe[k:])

    def test_same_matrix_for_every_position(self):
        pe = sinusoidal_encoding(30, 8, dtype=torch.float64)
        r = shift_matrix(3, 8)
        torch.testing.assert_close(pe[20] @ r, pe[23])
        torch.testing.assert_close(pe[0] @ r, pe[3])

    def test_rotation_properties(self):
        r = shift_matrix(7, 8)
        torch.testing.assert_close(r @ r.T, torch.eye(8, dtype=torch.float64))
        torch.testing.assert_close(shift_matrix(0, 8), torch.eye(8, dtype=torch.float64))
        torch.testing.assert_close(shift_matrix(2, 8) @ shift_matrix(3, 8), shift_matrix(5, 8))

    def test_odd_dimension_rejected(self):
        with pytest.raises(ValueError):
            shift_matrix(1, 5)
