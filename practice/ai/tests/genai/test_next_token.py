"""Checks exercises/genai/next_token.py - lesson how-llms-work."""

import math

import numpy as np
import pytest
from genai.next_token import bigram_probs, cross_entropy, generate, make_training_pairs, perplexity

pytestmark = pytest.mark.exercise

# A tiny synthetic SandPay "event log" at word level (fictional): ids of a 5-word vocabulary.
WORDS = ["<end>", "payment", "approved", "declined", "refund"]
END, PAYMENT, APPROVED, DECLINED, REFUND = range(5)
LOG = [PAYMENT, APPROVED, END, PAYMENT, APPROVED, END, PAYMENT, DECLINED, END, REFUND, APPROVED, END]


class TestTrainingPairs:
    def test_targets_are_the_inputs_shifted_by_one(self):
        X, Y = make_training_pairs([10, 11, 12, 13, 14], context=3)
        np.testing.assert_array_equal(X, [[10, 11, 12], [11, 12, 13]])
        np.testing.assert_array_equal(Y, [[11, 12, 13], [12, 13, 14]])

    def test_shapes_and_dtype(self):
        X, Y = make_training_pairs(LOG, context=4)
        assert X.shape == Y.shape == (len(LOG) - 4, 4)
        assert X.dtype == np.int64 and Y.dtype == np.int64

    def test_no_window_predicts_itself(self):
        X, Y = make_training_pairs(list(range(20)), context=5)
        assert not np.any(X == Y)

    @pytest.mark.parametrize("ids, context", [([1, 2, 3], 3), ([1, 2, 3], 0)])
    def test_rejects_too_short_or_empty_context(self, ids, context):
        with pytest.raises(ValueError):
            make_training_pairs(ids, context)


class TestBigram:
    def test_rows_sum_to_one(self):
        P = bigram_probs(LOG, vocab_size=5)
        np.testing.assert_allclose(P.sum(axis=1), np.ones(5))

    def test_counts_with_smoothing(self):
        P = bigram_probs(LOG, vocab_size=5, alpha=1.0)
        # after "payment": approved twice, declined once, plus 1 for each of 5 tokens -> (3, 2) out of 8
        assert P[PAYMENT, APPROVED] == pytest.approx(3 / 8)
        assert P[PAYMENT, DECLINED] == pytest.approx(2 / 8)
        assert P[PAYMENT, REFUND] == pytest.approx(1 / 8)

    def test_alpha_zero_gives_raw_frequencies(self):
        P = bigram_probs(LOG, vocab_size=5, alpha=0.0)
        assert P[PAYMENT, APPROVED] == pytest.approx(2 / 3)
        assert P[PAYMENT, END] == 0.0


class TestLoss:
    def test_cross_entropy_by_hand(self):
        probs = np.array([[0.5, 0.25, 0.25], [0.1, 0.8, 0.1]])
        assert cross_entropy(probs, [0, 1]) == pytest.approx(-(math.log(0.5) + math.log(0.8)) / 2)

    def test_uniform_guess_has_loss_ln_v_and_perplexity_v(self):
        probs = np.full((4, 39), 1 / 39)
        loss = cross_entropy(probs, [0, 5, 17, 38])
        assert loss == pytest.approx(math.log(39))
        assert perplexity(loss) == pytest.approx(39)

    def test_bigram_beats_uniform_on_the_log(self):
        P = bigram_probs(LOG, vocab_size=5)
        loss = cross_entropy(P[LOG[:-1]], LOG[1:])
        assert loss < math.log(5)
        assert perplexity(loss) == pytest.approx(math.exp(loss))


class TestGenerate:
    def test_greedy_follows_the_most_likely_token(self):
        P = bigram_probs(LOG, vocab_size=5)
        out = generate(lambda window: P[window[-1]], [PAYMENT], max_new_tokens=10, context=1, stop_id=END)
        assert out == [APPROVED, END]

    def test_model_only_sees_the_last_context_tokens(self):
        seen = []

        def fake(window):
            seen.append(list(window))
            return np.eye(5)[len(seen) % 5]

        prompt = [1, 2, 3, 4]
        generate(fake, prompt, max_new_tokens=3, context=2)
        assert seen == [[3, 4], [4, 1], [1, 2]]
        assert prompt == [1, 2, 3, 4]

    def test_returns_only_new_tokens_and_respects_max(self):
        out = generate(lambda w: np.eye(5)[DECLINED], [PAYMENT], max_new_tokens=4, context=8)
        assert out == [DECLINED] * 4

    def test_sampling_is_reproducible_with_a_seed(self):
        P = bigram_probs(LOG, vocab_size=5)
        runs = [generate(lambda w: P[w[-1]], [PAYMENT], 30, 1, rng=np.random.default_rng(3)) for _ in range(2)]
        assert runs[0] == runs[1]
        assert len(set(runs[0])) > 2
