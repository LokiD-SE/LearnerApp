"""Checks exercises/ml_foundations/linalg.py (lesson ml-maths-essentials)."""

import ast
import inspect

import numpy as np
import pytest
from ml_foundations import linalg
from ml_foundations.linalg import cosine_similarity, pairwise_sq_distances, predict_scores

pytestmark = pytest.mark.exercise


class TestCosineSimilarity:
    def test_parallel_vectors_score_one(self):
        assert cosine_similarity([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == pytest.approx(1.0)

    def test_opposite_vectors_score_minus_one(self):
        assert cosine_similarity([1.0, -2.0], [-3.0, 6.0]) == pytest.approx(-1.0)

    def test_orthogonal_vectors_score_zero(self):
        assert cosine_similarity([1.0, 0.0, 0.0], [0.0, 5.0, 0.0]) == pytest.approx(0.0)

    def test_known_angle(self):
        # 45 degrees: cos = 1 / sqrt(2)
        assert cosine_similarity([1.0, 0.0], [1.0, 1.0]) == pytest.approx(1 / np.sqrt(2))

    def test_ignores_length_but_not_direction(self):
        a = np.array([42.0, 1.5, 120.0])
        assert cosine_similarity(a, 10 * a) == pytest.approx(1.0)
        assert cosine_similarity(a, [40.0, 2.0, 110.0]) == pytest.approx(0.999913, abs=1e-6)

    def test_returns_a_python_float(self):
        assert type(cosine_similarity([1.0, 2.0], [3.0, 4.0])) is float

    def test_zero_vector_is_rejected(self):
        with pytest.raises(ValueError):
            cosine_similarity([0.0, 0.0], [1.0, 2.0])

    def test_different_lengths_are_rejected(self):
        with pytest.raises(ValueError):
            cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])

    def test_matrices_are_rejected(self):
        with pytest.raises(ValueError):
            cosine_similarity([[1.0, 2.0]], [[1.0, 2.0]])


class TestPredictScores:
    X = np.array([[42.0, 1.5], [40.0, 2.0], [95.0, 0.5], [12.0, 6.0]])
    w = np.array([0.02, 0.4])

    def test_one_score_per_row(self):
        scores = predict_scores(self.X, self.w, -1.0)
        assert scores.shape == (4,)
        np.testing.assert_allclose(scores, [0.44, 0.6, 1.1, 1.64])

    def test_matches_a_row_by_row_loop(self):
        rng = np.random.default_rng(0)
        X = rng.normal(size=(7, 3))
        w = rng.normal(size=3)
        expected = [sum(X[i, j] * w[j] for j in range(3)) + 0.5 for i in range(7)]
        np.testing.assert_allclose(predict_scores(X, w, 0.5), expected)

    def test_wrong_number_of_weights_names_the_shapes(self):
        with pytest.raises(ValueError, match=r"\(4, 2\)"):
            predict_scores(self.X, np.array([0.1, 0.2, 0.3]), 0.0)

    def test_column_vector_of_weights_is_rejected(self):
        with pytest.raises(ValueError):
            predict_scores(self.X, self.w.reshape(-1, 1), 0.0)

    def test_a_single_row_must_still_be_2d(self):
        with pytest.raises(ValueError):
            predict_scores(np.array([42.0, 1.5]), self.w, 0.0)


class TestPairwiseSqDistances:
    def test_small_example(self):
        A = np.array([[0.0, 0.0], [3.0, 4.0]])
        B = np.array([[0.0, 0.0], [6.0, 8.0], [3.0, 0.0]])
        np.testing.assert_allclose(
            pairwise_sq_distances(A, B), [[0.0, 100.0, 9.0], [25.0, 25.0, 16.0]], atol=1e-9
        )

    def test_matches_a_double_loop(self):
        rng = np.random.default_rng(1)
        A = rng.normal(size=(6, 4))
        B = rng.normal(size=(5, 4))
        expected = np.array([[np.sum((a - b) ** 2) for b in B] for a in A])
        result = pairwise_sq_distances(A, B)
        assert result.shape == (6, 5)
        np.testing.assert_allclose(result, expected, atol=1e-9)

    def test_never_negative(self):
        rng = np.random.default_rng(2)
        A = rng.normal(loc=1e4, size=(20, 3))
        assert (pairwise_sq_distances(A, A) >= 0).all()

    def test_different_feature_counts_are_rejected(self):
        with pytest.raises(ValueError):
            pairwise_sq_distances(np.zeros((2, 3)), np.zeros((2, 4)))

    def test_uses_no_python_loops(self):
        tree = ast.parse(inspect.getsource(linalg.pairwise_sq_distances))
        loops = [n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While, ast.comprehension))]
        assert loops == [], "vectorise with a matrix product and broadcasting instead of loops"
