"""Convolution by hand: output sizes, a naive 2D convolution layer, max pooling, parameter counts and the
receptive field of a stack of layers.

Lesson: Convolutional networks for computer vision (#/lesson/cnns-for-computer-vision). Exercise - the
reference solution is solutions/deep_learning/conv_shapes.py.
Arrays follow PyTorch's layout: a batch of images is (N, C, H, W) and a convolution weight is
(C_out, C_in, kH, kW). Only square kernels, strides and padding are used here.
"""

import numpy as np


def conv_output_size(size: int, kernel_size: int, stride: int = 1, padding: int = 0, dilation: int = 1) -> int:
    """Return the output height (or width) of a convolution or pooling layer along one dimension.

    The formula from the ``torch.nn.Conv2d`` documentation:

        out = floor((size + 2 * padding - dilation * (kernel_size - 1) - 1) / stride) + 1

    Raise ``ValueError`` when the result is smaller than 1 (the kernel does not fit even once).
    """
    raise NotImplementedError


def conv2d_naive(
    x: np.ndarray, weight: np.ndarray, bias: np.ndarray | None = None, stride: int = 1, padding: int = 0
) -> np.ndarray:
    """Compute what ``torch.nn.functional.conv2d`` computes, with loops and NumPy.

    ``x`` is (N, C_in, H, W), ``weight`` is (C_out, C_in, k, k), ``bias`` is (C_out,) or None. Pad the input
    with zeros on every side, then slide the kernel: each output value is the sum over all input channels
    and kernel positions of input * weight, plus the output channel's bias. Like every deep learning library,
    this is cross-correlation - the kernel is NOT flipped. Returns a float array (N, C_out, H_out, W_out).
    """
    # A colleague's draft. It runs, and with padding=0 the shapes are right - run the tests to see the rest.
    x = np.asarray(x, dtype=float)
    weight = np.asarray(weight, dtype=float)
    n, c_in, h, w = x.shape
    c_out, _, k, _ = weight.shape
    h_out = (h - k) // stride + 1
    w_out = (w - k) // stride + 1
    flipped = weight[:, :, ::-1, ::-1]  # "convolution flips the kernel" - the textbook definition
    out = np.zeros((n, c_out, h_out, w_out))
    for i in range(h_out):
        for j in range(w_out):
            patch = x[:, :, i * stride : i * stride + k, j * stride : j * stride + k]
            out[:, :, i, j] = np.tensordot(patch, flipped, axes=([1, 2, 3], [1, 2, 3]))
    if bias is not None:
        out += np.asarray(bias, dtype=float).reshape(1, c_out, 1, 1)
    return out


def max_pool2d_naive(x: np.ndarray, kernel_size: int, stride: int | None = None) -> np.ndarray:
    """Compute ``torch.nn.functional.max_pool2d`` (no padding, floor mode) on an (N, C, H, W) array.

    ``stride`` defaults to ``kernel_size``, as in PyTorch. Each channel is pooled on its own: the output keeps
    N and C and takes the maximum of every kernel_size x kernel_size window.
    """
    raise NotImplementedError


def conv_param_count(in_channels: int, out_channels: int, kernel_size: int, bias: bool = True) -> int:
    """Return the number of learnable parameters of ``nn.Conv2d(in_channels, out_channels, kernel_size)``.

    Every output channel has one kernel of in_channels x kernel_size x kernel_size weights, plus one bias.
    The count does not depend on the image size - that is parameter sharing.
    """
    # A colleague's draft.
    return out_channels * kernel_size * kernel_size + (out_channels if bias else 0)


def receptive_field(layers: list[tuple[int, int, int]]) -> int:
    """Return the receptive field (in input pixels, along one dimension) of one unit after a stack of layers.

    ``layers`` lists ``(kernel_size, stride, dilation)`` for each convolution or pooling layer, input first.
    Track two numbers while walking the stack: the receptive field ``r`` (starts at 1 - one pixel) and the
    ``jump`` - the distance in input pixels between neighbouring units of the current layer (starts at 1).
    A layer whose dilated kernel spans ``dilation * (kernel_size - 1) + 1`` units grows ``r`` by
    ``(span - 1) * jump``, then multiplies ``jump`` by its stride. An empty stack returns 1.
    """
    raise NotImplementedError
