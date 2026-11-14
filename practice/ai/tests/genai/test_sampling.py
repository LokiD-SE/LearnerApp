"""Checks exercises/genai/sampling.py - lesson how-llms-work."""

import numpy as np
import pytest
from genai.sampling import apply_temperature, sample_next, softmax, top_k_filter, top_p_filter

pytestmark = pytest.mark.exercise

# Real next-character logits (rounded) from the lesson's tiny character model after the prompt
# "payment 4721 ", trained on a synthetic SandPay event log. Index 17 is 'a' (approved), 20 is 'd' (declined).
VOCAB = list("\n .0123456789:?AQabcdefghiklmnoprstuvxy")
PAYMENT_LOGITS = np.array(
    [-0.33, 1.3, -4.29, -5.29, -1.5, -1.19, -1.79, -1.59, -1.62, -1.77, -2.03, -2.24, -1.81, -4.69, -4.14,
     -3.64, -3.44, 12.69, 0.47, -1.15, 11.44, -1.51, -0.54, -0.74, -1.48, -0.09, -6.18, -1.5, -1.34, -1.97,
     -1.04, 5.51, 3.02, 2.61, 0.58, -7.57, -2.35, -8.89, -3.83]
)
A, D, P = VOCAB.index("a"), VOCAB.index("d"), VOCAB.index("p")


def kept(filtered):
    return set(np.flatnonzero(np.isfinite(filtered)).tolist())


class TestTemperature:
    def test_divides_the_logits(self):
        np.testing.assert_allclose(apply_temperature(np.array([2.0, 1.0, -1.0]), 0.5), [4.0, 2.0, -2.0])

    def test_low_temperature_sharpens_and_high_flattens(self):
        p_low = softmax(apply_temperature(PAYMENT_LOGITS, 0.5))
        p_one = softmax(apply_temperature(PAYMENT_LOGITS, 1.0))
        p_high = softmax(apply_temperature(PAYMENT_LOGITS, 2.0))
        assert p_low[A] == pytest.approx(0.9241, abs=1e-3)
        assert p_one[A] == pytest.approx(0.7768, abs=1e-3)
        assert p_high[A] == pytest.approx(0.6227, abs=1e-3)

    def test_temperature_keeps_the_ranking(self):
        z = apply_temperature(PAYMENT_LOGITS, 3.0)
        assert np.array_equal(np.argsort(-z, kind="stable"), np.argsort(-PAYMENT_LOGITS, kind="stable"))

    @pytest.mark.parametrize("t", [0, -1.0])
    def test_rejects_non_positive(self, t):
        with pytest.raises(ValueError):
            apply_temperature(PAYMENT_LOGITS, t)


class TestTopK:
    def test_keeps_the_k_best(self):
        assert kept(top_k_filter(PAYMENT_LOGITS, 3)) == {A, D, P}

    def test_kept_logits_are_unchanged_and_input_is_not_modified(self):
        before = PAYMENT_LOGITS.copy()
        out = top_k_filter(PAYMENT_LOGITS, 2)
        assert out[A] == PAYMENT_LOGITS[A] and out[D] == PAYMENT_LOGITS[D]
        np.testing.assert_array_equal(PAYMENT_LOGITS, before)

    def test_ties_keep_the_lower_id(self):
        assert kept(top_k_filter(np.array([1.0, 3.0, 3.0, 3.0]), 2)) == {1, 2}

    def test_large_k_keeps_everything(self):
        assert kept(top_k_filter(PAYMENT_LOGITS, 1000)) == set(range(len(VOCAB)))

    def test_rejects_k_below_one(self):
        with pytest.raises(ValueError):
            top_k_filter(PAYMENT_LOGITS, 0)


class TestTopP:
    def test_smallest_set_reaching_p(self):
        # probabilities 0.5, 0.3, 0.2: p=0.7 needs the first two (0.5 alone is not enough)
        z = np.log(np.array([0.2, 0.5, 0.3]))
        assert kept(top_p_filter(z, 0.7)) == {1, 2}
        assert kept(top_p_filter(z, 0.8)) == {1, 2}
        assert kept(top_p_filter(z, 0.81)) == {0, 1, 2}

    def test_keeps_the_top_token_even_when_it_alone_exceeds_p(self):
        assert kept(top_p_filter(PAYMENT_LOGITS, 0.5)) == {A}

    def test_real_logits(self):
        assert kept(top_p_filter(PAYMENT_LOGITS, 0.9)) == {A, D}

    def test_p_one_keeps_every_token_with_nonzero_probability(self):
        assert kept(top_p_filter(np.array([0.0, 0.0, 0.0, 0.0]), 1.0)) == {0, 1, 2, 3}

    def test_input_is_not_modified(self):
        before = PAYMENT_LOGITS.copy()
        top_p_filter(PAYMENT_LOGITS, 0.9)
        np.testing.assert_array_equal(PAYMENT_LOGITS, before)

    @pytest.mark.parametrize("p", [0.0, 1.5])
    def test_rejects_p_outside_range(self, p):
        with pytest.raises(ValueError):
            top_p_filter(PAYMENT_LOGITS, p)


class TestSampleNext:
    def test_greedy_ignores_the_rng(self):
        assert sample_next(PAYMENT_LOGITS, rng=None, temperature=0) == A

    def test_greedy_tie_takes_the_lower_id(self):
        assert sample_next(np.array([0.0, 2.0, 2.0]), rng=None, temperature=0) == 1

    def test_frequencies_follow_the_softmax(self):
        rng = np.random.default_rng(0)
        draws = [sample_next(PAYMENT_LOGITS, rng) for _ in range(4000)]
        assert draws.count(A) / 4000 == pytest.approx(0.775, abs=0.03)
        assert draws.count(D) / 4000 == pytest.approx(0.224, abs=0.03)

    def test_top_k_one_is_greedy(self):
        rng = np.random.default_rng(1)
        assert {sample_next(PAYMENT_LOGITS, rng, temperature=2.0, top_k=1) for _ in range(50)} == {A}

    def test_filters_are_applied_after_temperature(self):
        # at T=2 the top two hold 0.956 of the mass, so top_p=0.95 keeps exactly 'a' and 'd'
        rng = np.random.default_rng(2)
        draws = {sample_next(PAYMENT_LOGITS, rng, temperature=2.0, top_p=0.95) for _ in range(300)}
        assert draws == {A, D}

    def test_same_seed_same_tokens(self):
        runs = []
        for _ in range(2):
            rng = np.random.default_rng(5)
            runs.append([sample_next(PAYMENT_LOGITS, rng, temperature=1.5) for _ in range(30)])
        assert runs[0] == runs[1]
        assert len(set(runs[0])) > 1
