"""Checks exercises/deep_learning/conv_shapes.py - lesson cnns-for-computer-vision."""

import numpy as np
import pytest
import torch
import torch.nn.functional as F
from deep_learning.conv_shapes import (
    conv2d_naive,
    conv_output_size,
    conv_param_count,
    max_pool2d_naive,
    receptive_field,
)
from torch import nn

pytestmark = pytest.mark.exercise


class TestConvOutputSize:
    @pytest.mark.parametrize(
        "size, kernel, stride, padding, dilation",
        [
            (8, 3, 1, 0, 1),
            (8, 3, 1, 1, 1),
            (8, 3, 2, 0, 1),
            (8, 3, 2, 1, 1),
            (8, 3, 1, 0, 2),
            (7, 3, 2, 0, 1),
            (10, 3, 2, 0, 1),
            (224, 11, 4, 0, 1),
            (227, 11, 4, 0, 1),
            (32, 5, 1, 2, 1),
            (5, 5, 1, 0, 1),
        ],
    )
    def test_matches_pytorch(self, size, kernel, stride, padding, dilation):
        conv = nn.Conv2d(1, 1, kernel, stride=stride, padding=padding, dilation=dilation)
        expected = conv(torch.zeros(1, 1, size, size)).shape[-1]
        assert conv_output_size(size, kernel, stride, padding, dilation) == expected

    def test_pooling_uses_same_formula(self):
        assert conv_output_size(7, 2, 2) == nn.MaxPool2d(2)(torch.zeros(1, 1, 7, 7)).shape[-1] == 3

    def test_kernel_too_big_raises(self):
        with pytest.raises(ValueError):
            conv_output_size(4, 5)


class TestConv2dNaive:
    def test_tiny_example_is_cross_correlation(self):
        x = np.arange(16.0).reshape(1, 1, 4, 4)
        w = np.array([[[[1.0, 2.0], [3.0, 4.0]]]])
        expected = np.array([[34.0, 44.0, 54.0], [74.0, 84.0, 94.0], [114.0, 124.0, 134.0]])
        np.testing.assert_allclose(conv2d_naive(x, w)[0, 0], expected)

    @pytest.mark.parametrize("stride, padding", [(1, 0), (1, 1), (2, 0), (2, 1), (3, 2)])
    def test_matches_torch_conv2d(self, stride, padding):
        torch.manual_seed(0)
        x = torch.randn(2, 3, 9, 9, dtype=torch.float64)
        w = torch.randn(4, 3, 3, 3, dtype=torch.float64)
        b = torch.randn(4, dtype=torch.float64)
        expected = F.conv2d(x, w, b, stride=stride, padding=padding).numpy()
        got = conv2d_naive(x.numpy(), w.numpy(), b.numpy(), stride=stride, padding=padding)
        assert got.shape == expected.shape
        np.testing.assert_allclose(got, expected, rtol=1e-10, atol=1e-10)

    def test_no_bias(self):
        torch.manual_seed(1)
        x = torch.randn(1, 2, 6, 6, dtype=torch.float64)
        w = torch.randn(3, 2, 5, 5, dtype=torch.float64)
        np.testing.assert_allclose(conv2d_naive(x.numpy(), w.numpy()), F.conv2d(x, w).numpy(), atol=1e-10)

    def test_does_not_modify_inputs(self):
        x = np.ones((1, 1, 5, 5))
        w = np.arange(9.0).reshape(1, 1, 3, 3)
        conv2d_naive(x, w, padding=1)
        assert x.shape == (1, 1, 5, 5) and np.all(x == 1.0)
        np.testing.assert_array_equal(w, np.arange(9.0).reshape(1, 1, 3, 3))


class TestMaxPool:
    @pytest.mark.parametrize("size, kernel, stride", [(8, 2, None), (7, 2, None), (9, 3, None), (8, 3, 2)])
    def test_matches_torch(self, size, kernel, stride):
        torch.manual_seed(2)
        x = torch.randn(2, 3, size, size, dtype=torch.float64)
        expected = F.max_pool2d(x, kernel, stride).numpy()
        got = max_pool2d_naive(x.numpy(), kernel, stride)
        assert got.shape == expected.shape
        np.testing.assert_allclose(got, expected)


class TestParamCount:
    @pytest.mark.parametrize(
        "c_in, c_out, k, bias", [(1, 16, 3, True), (3, 96, 11, True), (64, 64, 3, False), (16, 32, 5, True)]
    )
    def test_matches_pytorch(self, c_in, c_out, k, bias):
        conv = nn.Conv2d(c_in, c_out, k, bias=bias)
        assert conv_param_count(c_in, c_out, k, bias) == sum(p.numel() for p in conv.parameters())


def gradient_receptive_field(net: nn.Module, size: int = 41) -> int:
    """Measure the receptive field of the centre output unit by backpropagating from it."""
    inp = torch.zeros(1, 1, size, size, requires_grad=True)
    out = net(inp)
    out[0, 0, out.shape[2] // 2, out.shape[3] // 2].backward()
    rows = (inp.grad[0, 0].abs().sum(1) > 0).nonzero()
    return int(rows.max() - rows.min() + 1)


def ones_conv(k: int, stride: int = 1, dilation: int = 1) -> nn.Conv2d:
    conv = nn.Conv2d(1, 1, k, stride=stride, dilation=dilation, bias=False)
    nn.init.constant_(conv.weight, 1.0)
    return conv


class TestReceptiveField:
    def test_known_stacks(self):
        assert receptive_field([]) == 1
        assert receptive_field([(3, 1, 1)]) == 3
        assert receptive_field([(3, 1, 1)] * 3) == 7
        assert receptive_field([(3, 1, 1), (2, 2, 1), (3, 1, 1)]) == 8
        assert receptive_field([(3, 1, 2), (3, 1, 2)]) == 9

    @pytest.mark.parametrize(
        "spec",
        [
            [(3, 1, 1), (3, 1, 1)],
            [(3, 1, 1), (2, 2, 1), (3, 1, 1), (2, 2, 1), (3, 1, 1)],
            [(5, 2, 1), (3, 1, 1)],
            [(3, 1, 2), (3, 2, 1), (3, 1, 3)],
        ],
    )
    def test_matches_gradient_measurement(self, spec):
        layers = [nn.AvgPool2d(k, s) if (k == 2 and s == 2) else ones_conv(k, s, d) for k, s, d in spec]
        assert receptive_field(spec) == gradient_receptive_field(nn.Sequential(*layers))
