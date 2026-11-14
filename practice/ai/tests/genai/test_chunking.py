"""Checks exercises/genai/chunking.py - lesson retrieval-augmented-generation."""

import pytest
from genai.chunking import Chunk, chunk_by_heading, chunk_fixed, recall_at_k

pytestmark = pytest.mark.exercise

TEN = "w0 w1 w2 w3 w4 w5 w6 w7 w8 w9"

DOC = """\
Payouts move your balance to your bank.

## Payout schedule
New accounts are paid on a 7-day
rolling schedule.

## Empty section

## Failed payouts
A payout fails when the bank details are wrong.
"""


class TestChunkFixed:
    def test_no_overlap(self):
        chunks = chunk_fixed("d", TEN, 4)
        assert [c.text for c in chunks] == ["w0 w1 w2 w3", "w4 w5 w6 w7", "w8 w9"]
        assert [c.id for c in chunks] == ["d#0", "d#1", "d#2"]
        assert all(c.doc == "d" and c.heading == "" for c in chunks)

    def test_overlap_repeats_words(self):
        chunks = chunk_fixed("d", TEN, 4, 2)
        assert [c.text for c in chunks] == ["w0 w1 w2 w3", "w2 w3 w4 w5", "w4 w5 w6 w7", "w6 w7 w8 w9"]

    def test_no_window_of_only_overlap(self):
        # step 3: windows at 0, 3, 6; the one at 6 reaches the end, so there is no window at 9
        assert [c.text for c in chunk_fixed("d", TEN, 4, 1)] == ["w0 w1 w2 w3", "w3 w4 w5 w6", "w6 w7 w8 w9"]

    def test_whitespace_and_short_texts(self):
        assert [c.text for c in chunk_fixed("d", "  a\n b\t c ", 5)] == ["a b c"]
        assert chunk_fixed("d", "   ", 5) == []

    @pytest.mark.parametrize("size, overlap", [(0, 0), (4, 4), (4, 5), (4, -1)])
    def test_rejects_bad_parameters(self, size, overlap):
        with pytest.raises(ValueError):
            chunk_fixed("d", TEN, size, overlap)


class TestChunkByHeading:
    def test_sections_with_context_prefix(self):
        chunks = chunk_by_heading("payouts", "Payouts", DOC)
        assert chunks == [
            Chunk("payouts#0", "payouts", "", "Payouts: Payouts move your balance to your bank."),
            Chunk(
                "payouts#1",
                "payouts",
                "Payout schedule",
                "Payouts > Payout schedule: New accounts are paid on a 7-day rolling schedule.",
            ),
            Chunk(
                "payouts#2",
                "payouts",
                "Failed payouts",
                "Payouts > Failed payouts: A payout fails when the bank details are wrong.",
            ),
        ]

    def test_long_sections_are_split_and_keep_prefix(self):
        chunks = chunk_by_heading("d", "Doc", "## Long\n" + TEN, max_words=4)
        assert [c.text for c in chunks] == ["Doc > Long: w0 w1 w2 w3", "Doc > Long: w4 w5 w6 w7", "Doc > Long: w8 w9"]
        assert [c.id for c in chunks] == ["d#0", "d#1", "d#2"] and {c.heading for c in chunks} == {"Long"}

    def test_heading_needs_hash_hash_space(self):
        chunks = chunk_by_heading("d", "Doc", "#Not a heading\n### Not either\n## Yes\nbody")
        assert [c.heading for c in chunks] == ["", "Yes"]


class TestRecallAtK:
    def chunk(self, text):
        return Chunk("x#0", "x", "", text)

    def test_counts_queries_with_the_fact_in_the_top_k(self):
        results = [
            [self.chunk("Refunds take 5 to 10 business days.")],
            [self.chunk("nothing useful"), self.chunk("Evidence within 7 calendar   days.")],
        ]
        facts = ["5 TO 10 business days", "within 7 calendar days"]
        assert recall_at_k(results, facts, 1) == pytest.approx(0.5)
        assert recall_at_k(results, facts, 2) == pytest.approx(1.0)

    def test_a_fact_split_across_chunks_is_a_miss(self):
        results = [[self.chunk("reaches the customer within 5 to"), self.chunk("10 business days")]]
        assert recall_at_k(results, ["within 5 to 10 business days"], 2) == 0.0

    def test_bad_input(self):
        assert recall_at_k([], [], 3) == 0.0
        with pytest.raises(ValueError):
            recall_at_k([[]], [], 3)
        with pytest.raises(ValueError):
            recall_at_k([[]], ["x"], 0)

    def test_overlap_rescues_a_fact_on_a_boundary(self):
        text = "aa bb cc dd fact one two ee ff gg"
        no_overlap = chunk_fixed("d", text, 5)
        overlap = chunk_fixed("d", text, 5, 2)
        assert recall_at_k([no_overlap], ["fact one two"], 5) == 0.0
        assert recall_at_k([overlap], ["fact one two"], 5) == 1.0
