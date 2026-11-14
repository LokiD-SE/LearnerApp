"""Checks exercises/ml_foundations/probability.py (lesson ml-maths-essentials)."""

import numpy as np
import pytest
from ml_foundations.probability import expectation_and_variance, normal_pdf, posterior

pytestmark = pytest.mark.exercise


class TestPosterior:
    def test_rare_fraud_with_a_good_detector(self):
        # 0.2% fraud, 95% of fraud flagged, 3% of legitimate payments flagged
        assert posterior(0.002, 0.95, 0.03) == pytest.approx(0.0597, abs=1e-4)

    def test_agrees_with_a_simulation(self):
        rng = np.random.default_rng(42)
        n = 400_000
        fraud = rng.random(n) < 0.05
        flagged = np.where(fraud, rng.random(n) < 0.9, rng.random(n) < 0.1)
        simulated = (fraud & flagged).sum() / flagged.sum()
        assert posterior(0.05, 0.9, 0.1) == pytest.approx(simulated, abs=0.01)

    def test_a_useless_test_leaves_the_prior_unchanged(self):
        # If the flag fires equally often either way, it carries no information
        assert posterior(0.3, 0.4, 0.4) == pytest.approx(0.3)

    def test_no_false_positives_means_certainty(self):
        assert posterior(0.01, 0.5, 0.0) == pytest.approx(1.0)

    def test_returns_a_python_float(self):
        assert type(posterior(0.1, 0.9, 0.2)) is float

    @pytest.mark.parametrize("args", [(1.2, 0.9, 0.1), (0.1, -0.1, 0.1), (0.1, 0.9, 1.5)])
    def test_probabilities_outside_0_1_are_rejected(self, args):
        with pytest.raises(ValueError):
            posterior(*args)

    def test_impossible_evidence_is_rejected(self):
        with pytest.raises(ValueError):
            posterior(0.5, 0.0, 0.0)


class TestExpectationAndVariance:
    def test_refund_amounts(self):
        mean, var = expectation_and_variance([0.0, 10.0, 50.0], [0.90, 0.08, 0.02])
        assert mean == pytest.approx(1.8)
        assert var == pytest.approx(54.76)
        assert type(mean) is float and type(var) is float

    def test_fair_die(self):
        mean, var = expectation_and_variance([1, 2, 3, 4, 5, 6], [1 / 6] * 6)
        assert mean == pytest.approx(3.5)
        assert var == pytest.approx(35 / 12)

    def test_a_certain_value_has_no_variance(self):
        assert expectation_and_variance([7.0, 9.0], [1.0, 0.0]) == pytest.approx((7.0, 0.0))

    def test_probabilities_must_sum_to_one(self):
        with pytest.raises(ValueError):
            expectation_and_variance([1.0, 2.0], [0.5, 0.6])

    def test_negative_probabilities_are_rejected(self):
        with pytest.raises(ValueError):
            expectation_and_variance([1.0, 2.0, 3.0], [1.2, -0.1, -0.1])

    def test_mismatched_lengths_are_rejected(self):
        with pytest.raises(ValueError):
            expectation_and_variance([1.0, 2.0, 3.0], [0.5, 0.5])


class TestNormalPdf:
    def test_standard_normal_peak(self):
        assert normal_pdf(0.0) == pytest.approx(1 / np.sqrt(2 * np.pi))

    def test_shifted_and_scaled(self):
        assert normal_pdf(35.0, mu=35.0, sigma=8.0) == pytest.approx(0.04987, abs=1e-5)
        assert normal_pdf(51.0, mu=35.0, sigma=8.0) == pytest.approx(0.00675, abs=1e-5)

    def test_symmetric_about_the_mean(self):
        assert normal_pdf(2.0, mu=5.0, sigma=2.0) == pytest.approx(normal_pdf(8.0, mu=5.0, sigma=2.0))

    def test_works_on_arrays(self):
        xs = np.array([-1.0, 0.0, 1.0])
        result = normal_pdf(xs)
        assert result.shape == (3,)
        np.testing.assert_allclose(result, np.exp(-0.5 * xs**2) / np.sqrt(2 * np.pi))

    def test_integrates_to_one(self):
        xs = np.linspace(-40, 110, 300_001)
        area = np.trapezoid(normal_pdf(xs, mu=35.0, sigma=8.0), xs)
        assert area == pytest.approx(1.0, abs=1e-9)

    @pytest.mark.parametrize("sigma", [0.0, -1.0])
    def test_non_positive_sigma_is_rejected(self, sigma):
        with pytest.raises(ValueError):
            normal_pdf(0.0, sigma=sigma)
