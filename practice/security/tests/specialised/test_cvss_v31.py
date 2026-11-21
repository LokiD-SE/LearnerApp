"""Checks exercises/specialised/cvss_v31.py: the CVSS v3.1 base score, against the vectors FIRST published."""

import pytest
import cvss_fixture as fx
from specialised.cvss_v31 import base_score, parse_vector, roundup

pytestmark = pytest.mark.exercise


def test_every_published_example_scores_as_published():
    wrong = {v: (want, base_score(v)) for v, want in fx.V31_PUBLISHED.items() if base_score(v) != want}
    assert wrong == {}


def test_a_vector_is_parsed_into_its_eight_metrics_in_any_order():
    expected = {"AV": "N", "AC": "L", "PR": "H", "UI": "N", "S": "U", "C": "L", "I": "L", "A": "N"}
    assert parse_vector("CVSS:3.1/AV:N/AC:L/PR:H/UI:N/S:U/C:L/I:L/A:N") == expected
    # the specification calls this ordering non-preferred but valid
    assert parse_vector("CVSS:3.1/S:U/AV:N/AC:L/PR:H/UI:N/C:L/I:L/A:N") == expected


@pytest.mark.parametrize("bad", [
    "AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",                      # no prefix
    "CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",             # another version
    "CVSS:3.1/AV:F/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",             # F is not an Attack Vector
    "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H",                 # A is missing
    "CVSS:3.1/AV:N/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",        # AV twice
    "CVSS:3.1/av:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",             # names are case sensitive
    "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H/E:F",         # temporal metrics are out of scope here
])
def test_a_bad_vector_is_rejected(bad):
    with pytest.raises(ValueError):
        parse_vector(bad)
    with pytest.raises(ValueError):
        base_score(bad)


def test_roundup_goes_up_to_one_decimal_place():
    assert roundup(4.02) == 4.1
    assert roundup(4.00) == 4.0
    assert roundup(0.0) == 0.0
    assert roundup(9.91) == 10.0


def test_roundup_ignores_floating_point_noise():
    assert roundup(4.000000000001) == 4.0      # a plain ceil(x * 10) / 10 would give 4.1
    assert roundup(0.1 + 0.2 + 0.1) == 0.4        # a hair above 0.4 in binary floating point
    assert roundup(7.000000000001) == 7.0


def test_no_impact_scores_zero():
    assert base_score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N") == 0.0
    assert base_score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:N/I:N/A:N") == 0.0


def test_a_changed_scope_raises_the_score_and_the_privileges_weight():
    unchanged = base_score("CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H")
    changed = base_score("CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H")
    assert (unchanged, changed) == (8.8, 9.9)


def test_the_score_never_exceeds_ten():
    assert base_score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H") == 10.0


def test_the_environment_you_assume_does_not_change_the_base_score():
    # the same metrics always give the same score: no clock, no state
    v = "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"
    assert {base_score(v) for _ in range(5)} == {6.5}
