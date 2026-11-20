"""Checks exercises/web/sess_entropy.py: hand-built samples first, then ids collected from the service."""

import pytest
from sess_fixture import make_app, serve
from web.sess_entropy import analyse_ids, classify_alphabet, collect_ids, is_sequential, is_weak

pytestmark = pytest.mark.exercise


def test_alphabets():
    assert classify_alphabet(["0123", "9876"]) == "decimal"
    assert classify_alphabet(["0a1F", "beef"]) == "hex"
    assert classify_alphabet(["Ab-_9z", "Qq_x0-"]) == "base64url"
    assert classify_alphabet(["a.b", "c+d"]) == "other"


def test_cheat_sheet_example_half_fixed_hex_is_32_bits():
    # 16 hex characters, the first 8 fixed: only 8 x 4 = 32 bits vary (OWASP cheat sheet example).
    ids = ["deadbeef" + f"{n:08x}" for n in (0x1A2B3C4D, 0x9F8E7D6C, 0x00FF00FF, 0x12EF34CD)]
    r = analyse_ids(ids)
    assert r.alphabet == "hex" and r.fixed_positions == list(range(8))
    assert r.estimated_bits == 32.0
    assert "below-64-bits" in r.findings and is_weak(r)


def test_sequential_and_duplicates():
    assert is_sequential(["s0003e9", "s0003ea", "s0003eb"]) is True
    assert is_sequential(["s0003e9", "s0103ea", "s0003eb"]) is False
    r = analyse_ids(["abc", "abc", "abd"])
    assert r.duplicates == 1 and "duplicates" in r.findings


def test_needs_two_samples():
    with pytest.raises(ValueError):
        analyse_ids(["only-one"])


def test_predictable_ids_from_the_service_are_weak():
    with serve(make_app()) as base:
        ids = collect_ids(base, 20)
    r = analyse_ids(ids)
    assert len(set(ids)) == 20
    assert r.sequential is True and r.estimated_bits < 64 and is_weak(r)


def test_random_ids_from_the_fixed_service_pass():
    with serve(make_app({"predictable-ids"})) as base:
        ids = collect_ids(base, 50)
    r = analyse_ids(ids)
    assert r.alphabet == "base64url" and r.lengths == (22, 22)
    assert r.estimated_bits >= 64 and not r.sequential and r.duplicates == 0
    assert not is_weak(r)
