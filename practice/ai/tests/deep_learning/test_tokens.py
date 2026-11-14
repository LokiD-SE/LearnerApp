"""Checks exercises/deep_learning/tokens.py - lesson sequence-models-and-embeddings."""

import pytest
import torch
from deep_learning.tokens import (
    END_OF_WORD,
    PAD,
    UNK,
    bpe_segment,
    build_vocab,
    encode,
    learn_bpe,
    pad_batch,
    tokenize,
)

pytestmark = pytest.mark.exercise

# Synthetic SandPay support-ticket snippets (written for these tests).
TICKETS = [
    "Refund failed for order 1042.",
    "Refund pending, customer asked again!",
    "Chargeback opened for order 1042.",
    "Customer asked for a refund.",
]


class TestTokenize:
    def test_lower_cases_and_splits_punctuation(self):
        assert tokenize("Refund of EUR 12.50 failed!") == ["refund", "of", "eur", "12", ".", "50", "failed", "!"]

    def test_whitespace_only_gives_no_tokens(self):
        assert tokenize("  \n\t ") == []

    def test_keeps_underscored_ids_together(self):
        assert tokenize("Merchant m_204, refund.") == ["merchant", "m_204", ",", "refund", "."]


class TestBuildVocab:
    def test_specials_first_then_frequency_then_alphabetical(self):
        vocab = build_vocab(["b a b", "c a b"])
        assert vocab == {PAD: 0, UNK: 1, "b": 2, "a": 3, "c": 4}

    def test_min_freq_drops_rare_tokens(self):
        vocab = build_vocab(TICKETS, min_freq=2)
        assert set(vocab) == {PAD, UNK, ".", "1042", "asked", "customer", "for", "order", "refund"}
        # ".", "for" and "refund" each appear 3 times: the tie is broken alphabetically ("." sorts first)
        assert [vocab["."], vocab["for"], vocab["refund"]] == [2, 3, 4]

    def test_max_size_counts_the_specials(self):
        vocab = build_vocab(TICKETS, max_size=4)
        assert vocab == {PAD: 0, UNK: 1, ".": 2, "for": 3}

    def test_ids_are_contiguous(self):
        vocab = build_vocab(TICKETS)
        assert sorted(vocab.values()) == list(range(len(vocab)))

    def test_max_size_below_two_is_rejected(self):
        with pytest.raises(ValueError):
            build_vocab(TICKETS, max_size=1)


class TestEncode:
    def test_known_tokens(self):
        vocab = build_vocab(TICKETS)
        assert encode("Refund asked.", vocab) == [vocab["refund"], vocab["asked"], vocab["."]]

    def test_unknown_tokens_become_unk(self):
        vocab = build_vocab(TICKETS, min_freq=2)
        assert encode("Chargeback refund reversed", vocab) == [1, vocab["refund"], 1]


class TestPadBatch:
    def test_shapes_values_mask_and_lengths(self):
        ids, mask, lengths = pad_batch([[5, 6, 7], [8], [9, 10]])
        assert ids.dtype == torch.long and mask.dtype == torch.bool and lengths.dtype == torch.long
        assert ids.tolist() == [[5, 6, 7], [8, 0, 0], [9, 10, 0]]
        assert mask.tolist() == [[True, True, True], [True, False, False], [True, True, False]]
        assert lengths.tolist() == [3, 1, 2]

    def test_custom_pad_id(self):
        ids, mask, _ = pad_batch([[5, 6], [7]], pad_id=99)
        assert ids.tolist() == [[5, 6], [7, 99]]
        assert mask.tolist() == [[True, True], [True, False]]

    def test_mask_comes_from_lengths_not_from_the_pad_value(self):
        # id 0 inside a sequence is a real token when the pad id is something else
        _, mask, _ = pad_batch([[0, 4], [3]], pad_id=9)
        assert mask.tolist() == [[True, True], [True, False]]

    def test_truncates_to_max_len(self):
        ids, mask, lengths = pad_batch([[1, 2, 3, 4, 5], [6, 7]], max_len=3)
        assert ids.tolist() == [[1, 2, 3], [6, 7, 0]]
        assert lengths.tolist() == [3, 2]
        assert mask.sum().item() == 5

    def test_does_not_change_its_input(self):
        seqs = [[1, 2, 3], [4]]
        pad_batch(seqs, max_len=2)
        assert seqs == [[1, 2, 3], [4]]


class TestBPE:
    def test_merges_most_frequent_pairs_with_alphabetical_ties(self):
        assert learn_bpe({"low": 5, "lower": 2}, 2) == [("l", "o"), ("lo", "w")]

    def test_counts_are_weighted_by_word_frequency(self):
        # ("e", "r") occurs once in each word but "newer" is frequent; ("w", "e") is in both words too
        merges = learn_bpe({"newer": 6, "wider": 3}, 3)
        assert merges == [("e", "r"), ("er", END_OF_WORD), ("e", "w")]

    def test_stops_when_no_pairs_are_left(self):
        merges = learn_bpe({"ab": 3}, 10)
        assert merges == [("a", "b"), ("ab", END_OF_WORD)]

    def test_segment_applies_merges_in_learned_order(self):
        assert bpe_segment("lowest", [("l", "o"), ("lo", "w")]) == ["low", "e", "s", "t", END_OF_WORD]

    def test_unseen_word_is_built_from_learned_subwords(self):
        corpus = {"refund": 10, "refunded": 4, "funded": 3, "charge": 6, "charged": 5}
        merges = learn_bpe(corpus, 12)
        assert "".join(bpe_segment("refunded", merges)) == "refunded" + END_OF_WORD
        pieces = bpe_segment("recharged", merges)
        assert "".join(pieces) == "recharged" + END_OF_WORD
        assert len(pieces) < len("recharged") + 1  # some merges were reused
        assert bpe_segment("zz", merges) == ["z", "z", END_OF_WORD]
