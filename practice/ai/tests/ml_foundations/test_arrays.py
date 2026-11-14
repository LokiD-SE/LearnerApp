"""Checks exercises/ml_foundations/arrays.py - lesson python-numpy-pandas."""

import time

import numpy as np
import pytest
from ml_foundations.arrays import flag_over_limit, one_hot, pairwise_sq_distances, standardise

pytestmark = pytest.mark.exercise


class TestStandardise:
    def test_columns_have_mean_0_and_std_1(self):
        X = np.array([[2500.0, 3.0], [1999.0, 1.0], [120.0, 7.0], [48000.0, 2.0]])
        Z = standardise(X)
        np.testing.assert_allclose(Z.mean(axis=0), [0.0, 0.0], atol=1e-12)
        np.testing.assert_allclose(Z.std(axis=0), [1.0, 1.0])

    def test_uses_the_population_standard_deviation(self):
        Z = standardise(np.array([[1.0], [3.0]]))
        np.testing.assert_allclose(Z[:, 0], [-1.0, 1.0])

    def test_constant_column_becomes_zeros_not_nan(self):
        Z = standardise(np.array([[5.0, 1.0], [5.0, 2.0], [5.0, 3.0]]))
        assert not np.isnan(Z).any()
        np.testing.assert_array_equal(Z[:, 0], [0.0, 0.0, 0.0])

    def test_integer_input_gives_floats(self):
        Z = standardise(np.array([[1, 10], [3, 30]]))
        assert Z.dtype == np.float64
        np.testing.assert_allclose(Z, [[-1.0, -1.0], [1.0, 1.0]])

    def test_does_not_change_its_input(self):
        X = np.array([[1.0, 2.0], [3.0, 4.0]])
        before = X.copy()
        standardise(X)
        np.testing.assert_array_equal(X, before)


class TestOneHot:
    def test_one_column_per_class(self):
        np.testing.assert_array_equal(
            one_hot(np.array([2, 0, 1, 2]), 3),
            [[0, 0, 1], [1, 0, 0], [0, 1, 0], [0, 0, 1]],
        )

    def test_shape_and_dtype(self):
        out = one_hot(np.array([0, 1]), 4)
        assert out.shape == (2, 4)
        assert out.dtype == np.float64

    @pytest.mark.parametrize("labels", [[0, 3], [-1, 0]])
    def test_rejects_labels_out_of_range(self, labels):
        with pytest.raises(ValueError):
            one_hot(np.array(labels), 3)


class TestPairwiseSqDistances:
    def test_small_example(self):
        A = np.array([[0.0, 0.0], [1.0, 1.0]])
        B = np.array([[3.0, 4.0], [0.0, 1.0], [1.0, 1.0]])
        np.testing.assert_allclose(pairwise_sq_distances(A, B), [[25.0, 1.0, 2.0], [13.0, 1.0, 0.0]])

    def test_matches_a_slow_reference(self):
        rng = np.random.default_rng(42)
        A, B = rng.normal(size=(7, 3)), rng.normal(size=(5, 3))
        slow = np.array([[((a - b) ** 2).sum() for b in B] for a in A])
        np.testing.assert_allclose(pairwise_sq_distances(A, B), slow)

    def test_rejects_rows_of_different_length(self):
        with pytest.raises(ValueError):
            pairwise_sq_distances(np.ones((2, 3)), np.ones((2, 4)))

    def test_is_vectorised(self):
        # 400 x 400 pairs: broadcasting takes a few milliseconds, a Python double loop about a second.
        rng = np.random.default_rng(0)
        A, B = rng.normal(size=(400, 8)), rng.normal(size=(400, 8))
        start = time.perf_counter()
        out = pairwise_sq_distances(A, B)
        assert out.shape == (400, 400)
        assert time.perf_counter() - start < 0.25


class TestFlagOverLimit:
    def test_looks_up_each_merchants_limit(self):
        limits = np.array([10_000, 500, 2_000])
        amounts = np.array([9_999, 600, 2_000, 10_001, 400])
        merchant_idx = np.array([0, 1, 2, 0, 1])
        np.testing.assert_array_equal(
            flag_over_limit(amounts, merchant_idx, limits), [False, True, False, True, False]
        )

    def test_returns_a_boolean_array(self):
        out = flag_over_limit(np.array([1, 2]), np.array([0, 0]), np.array([1]))
        assert out.dtype == np.bool_
