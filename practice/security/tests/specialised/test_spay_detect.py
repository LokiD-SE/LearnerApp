"""Checks exercises/specialised/spay_detect.py: Luhn, masking, finding and redacting card numbers."""

import re

import pytest
import spay_fixture as fx
from specialised.spay_detect import PanHit, find_pans, luhn_valid, mask_pan, redact

pytestmark = pytest.mark.exercise

LONG_RUN = re.compile(r"[0-9]{10,}")


def pan(length=16, seed=1, prefix="4"):
    return fx.make_test_pan(prefix, length, seed)


@pytest.mark.parametrize("length", [13, 14, 15, 16, 17, 18, 19])
def test_luhn_accepts_generated_numbers_of_every_length(length):
    assert luhn_valid(pan(length)) is True


@pytest.mark.parametrize("seed", range(1, 8))
def test_luhn_rejects_a_changed_last_digit(seed):
    assert luhn_valid(fx.break_luhn(pan(16, seed))) is False


def test_luhn_rejects_a_swapped_pair_of_neighbours_when_the_digits_differ():
    good = pan(16, 3)
    for i in range(len(good) - 2):  # the last pair is excluded: swapping 0 and 9 is the known blind spot
        if good[i] != good[i + 1] and {good[i], good[i + 1]} != {"0", "9"}:
            swapped = good[:i] + good[i + 1] + good[i] + good[i + 2:]
            assert luhn_valid(swapped) is False


@pytest.mark.parametrize("text", ["", "7", "abcd", "12a4", "1234 5678"])
def test_luhn_rejects_what_is_not_digits_or_too_short(text):
    assert luhn_valid(text) is False


@pytest.mark.parametrize("length, shown_first, shown_last", [(13, 6, 3), (14, 6, 4), (15, 6, 4), (16, 6, 4), (19, 6, 4)])
def test_mask_keeps_the_first_six_and_the_last_four_but_hides_at_least_four(length, shown_first, shown_last):
    digits = pan(length)
    masked = mask_pan(digits)
    assert len(masked) == length
    assert masked[:shown_first] == digits[:shown_first]
    assert masked[length - shown_last:] == digits[length - shown_last:]
    assert masked.count("*") == length - shown_first - shown_last >= 4


@pytest.mark.parametrize("bad", ["", "123456789012", "1" * 20, "-".join(["1" * 4] * 4), "abcdefghijklmnop"])
def test_mask_rejects_anything_that_is_not_13_to_19_digits(bad):
    with pytest.raises(ValueError):
        mask_pan(bad)


def test_find_a_plain_pan_and_report_where_it_is():
    digits = pan(16, 1)
    text = f"card={digits} amount=25"
    hits = find_pans(text)
    assert len(hits) == 1
    hit = hits[0]
    assert isinstance(hit, PanHit)
    assert (hit.start, hit.end, hit.length) == (5, 21, 16)
    assert hit.masked == mask_pan(digits)
    assert text[hit.start:hit.end] == digits


def test_a_hit_never_holds_the_full_number():
    digits = pan(16, 2)
    for hit in find_pans(f"x {digits} y"):
        assert digits not in repr(hit)
        assert not LONG_RUN.search(repr(hit))


@pytest.mark.parametrize("separator", [" ", "-"])
def test_find_a_pan_written_in_groups(separator):
    digits = pan(16, 4)
    grouped = separator.join(digits[i:i + 4] for i in range(0, 16, 4))
    text = f"paid with {grouped}."
    (hit,) = find_pans(text)
    assert text[hit.start:hit.end] == grouped
    assert hit.length == 16
    assert hit.masked == mask_pan(digits)


@pytest.mark.parametrize("length", [13, 15, 16, 19])
def test_find_pans_of_the_lengths_a_card_can_have(length):
    (hit,) = find_pans(f"[{pan(length)}]")
    assert hit.length == length


def test_a_long_number_that_fails_the_luhn_check_is_not_a_hit():
    assert find_pans(f"order {fx.break_luhn(pan(16, 5))} shipped") == []


def test_a_run_longer_than_19_digits_is_not_cut_into_a_hit():
    twenty = pan(19, 6) + "7"
    assert find_pans(f"id {twenty}") == []
    assert find_pans(f"id 7{pan(19, 6)}") == []


def test_a_number_inside_a_longer_word_of_digits_and_letters_is_still_found_by_its_digits():
    (hit,) = find_pans(f"pan:{pan(16, 7)};")
    assert hit.length == 16


def test_short_numbers_and_dates_are_not_hits():
    assert find_pans("2026-11-21 10:15:30 order 12345 total 25.00") == []


def test_two_pans_in_one_line_are_both_found_in_order():
    first, second = pan(16, 1), pan(15, 2, "37")
    hits = find_pans(f"{first} then {second}")
    assert [h.length for h in hits] == [16, 15]
    assert hits[0].end < hits[1].start


def test_a_scanner_cannot_tell_a_card_from_any_long_number_that_passes_luhn():
    # not a card, just a 16-digit id that happens to pass the check: the scanner reports it (a candidate, not proof)
    lucky = pan(16, 99, "9")
    assert len(find_pans(f"ticket {lucky}")) == 1


def test_redact_replaces_every_hit_and_leaves_the_rest_alone():
    first, second = pan(16, 1), pan(16, 2)
    text = f"a={first}; b={second}; note=order 12345"
    out = redact(text)
    assert out == f"a={mask_pan(first)}; b={mask_pan(second)}; note=order 12345"
    assert first not in out and second not in out


def test_redacted_text_has_no_long_run_of_digits_left():
    digits = pan(19, 3)
    grouped = " ".join(digits[i:i + 4] for i in range(0, 16, 4)) + " " + digits[16:]
    out = redact(f"x {digits} y {grouped} z")
    assert not re.search(r"\b(?:\d[ -]?){13,19}\b", out)


def test_redact_returns_text_without_a_pan_unchanged():
    text = "nothing to see: 4242 and 12345678"
    assert redact(text) == text
