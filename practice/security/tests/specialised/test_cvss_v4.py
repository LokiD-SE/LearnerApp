"""Checks exercises/specialised/cvss_v4.py: CVSS v4.0 vector rules, the macro vector and the base score."""

import pytest
import cvss_fixture as fx
from cvss_data import LOOKUP
from specialised.cvss_v4 import macrovector, parse_vector, score

pytestmark = pytest.mark.exercise

NETWORK_HIGH = "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"


def test_every_published_example_scores_as_published():
    wrong = {v: (want, score(v)) for v, want in fx.V4_PUBLISHED.items() if score(v) != want}
    assert wrong == {}


def test_a_valid_vector_gives_its_metrics_and_a_default_exploit_maturity():
    m = parse_vector("CVSS:4.0/AV:N/AC:L/AT:N/PR:H/UI:N/VC:L/VI:L/VA:N/SC:N/SI:N/SA:N")
    assert m == {"AV": "N", "AC": "L", "AT": "N", "PR": "H", "UI": "N", "VC": "L", "VI": "L", "VA": "N",
                 "SC": "N", "SI": "N", "SA": "N", "E": "X"}
    assert parse_vector(NETWORK_HIGH + "/E:A")["E"] == "A"


@pytest.mark.parametrize("bad", [
    "CVSS:4.0/AV:F/AC:L/AT:N/PR:N/UI:N/VC:N/VI:L/VA:N/SC:N/SI:N/SA:N",       # F is not a valid AV
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:N/SA:N/E:A/E:X",  # E twice
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/ui:N/VC:N/VI:L/VA:N/SC:N/SI:N/SA:N",       # "ui" is not a metric
    "AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:L/VA:N/SC:N/SI:N/SA:N",                # no prefix
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:L/SC:N/SI:N/SA:N",            # VA is missing
    "CVSS:4.0/AC:L/AV:N/AT:N/PR:N/UI:N/VC:N/VI:L/VA:N/SC:N/SI:N/SA:N",       # order matters in v4.0
    "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",                          # a v3.1 vector
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N/E:Z",   # Z is not an E value
])
def test_a_bad_vector_is_rejected(bad):
    with pytest.raises(ValueError):
        parse_vector(bad)
    with pytest.raises(ValueError):
        score(bad)


@pytest.mark.parametrize("vector, macro", [
    (NETWORK_HIGH, "000200"),
    ("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H", "000100"),
    (NETWORK_HIGH + "/E:P", "000210"),
    (NETWORK_HIGH + "/E:U", "000220"),
    (NETWORK_HIGH + "/E:X", "000200"),
    ("CVSS:4.0/AV:L/AC:L/AT:N/PR:H/UI:N/VC:H/VI:H/VA:N/SC:N/SI:N/SA:N", "100200"),
    ("CVSS:4.0/AV:P/AC:H/AT:P/PR:H/UI:A/VC:L/VI:L/VA:L/SC:N/SI:N/SA:N", "212201"),
    ("CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N", "101200"),
])
def test_the_six_equivalence_classes(vector, macro):
    assert macrovector(parse_vector(vector)) == macro


def test_every_macro_vector_the_function_returns_is_in_the_lookup_table():
    for av in "NALP":
        for pr in "NLH":
            for vc in "HLN":
                v = f"CVSS:4.0/AV:{av}/AC:L/AT:N/PR:{pr}/UI:N/VC:{vc}/VI:N/VA:N/SC:N/SI:H/SA:N"
                assert macrovector(parse_vector(v)) in LOOKUP


def test_no_impact_on_any_system_scores_zero():
    assert score("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:N/SA:N") == 0.0


def test_a_score_never_exceeds_its_macro_vector_row_and_stays_on_the_scale():
    for vector in fx.V4_PUBLISHED:
        m = parse_vector(vector)
        assert 0.0 <= score(vector) <= LOOKUP[macrovector(m)] <= 10.0


def test_exploit_maturity_lowers_the_score_only_when_it_is_less_than_attacked():
    base = score(NETWORK_HIGH)
    assert score(NETWORK_HIGH + "/E:A") == base == score(NETWORK_HIGH + "/E:X")
    assert score(NETWORK_HIGH + "/E:P") < base
    assert score(NETWORK_HIGH + "/E:U") < score(NETWORK_HIGH + "/E:P")
