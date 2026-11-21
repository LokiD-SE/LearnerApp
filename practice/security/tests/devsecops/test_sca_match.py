"""Checks exercises/devsecops/sca_match.py: version ranges, matching, severity and priority."""

import pytest
import sca_fixture as fx
from devsecops.sca_inventory import Component, parse_cyclonedx
from devsecops.sca_match import (
    Finding,
    check,
    ecosystem_of,
    find_findings,
    parse_version,
    priority,
    rating,
    triage,
)

pytestmark = pytest.mark.exercise


def semver(*events):
    return [{"type": "SEMVER", "events": list(events)}]


def test_parse_version():
    assert parse_version("1.4.2") == (1, 4, 2)
    assert parse_version("10") == (10,)


@pytest.mark.parametrize("text", ["", "v1.2", "1.4.2rc1", "1..2", "1.2.", "one"])
def test_parse_version_rejects_anything_but_dots_and_digits(text):
    with pytest.raises(ValueError):
        parse_version(text)


def test_versions_compare_as_numbers_not_strings():
    ranges = semver({"introduced": "2.0.0"}, {"fixed": "2.10.0"})
    assert check("2.9.0", ranges) == (True, "2.10.0")  # "2.9.0" > "2.10.0" as text, but it is older
    assert check("2.10.0", ranges) == (False, "")


def test_introduced_is_inclusive_and_fixed_is_exclusive():
    ranges = semver({"introduced": "1.2.0"}, {"fixed": "1.4.2"})
    assert check("1.1.9", ranges) == (False, "")
    assert check("1.2.0", ranges) == (True, "1.4.2")
    assert check("1.4.1", ranges) == (True, "1.4.2")
    assert check("1.4.2", ranges) == (False, "")


def test_introduced_zero_matches_everything_before_the_fix():
    ranges = semver({"introduced": "0"}, {"fixed": "0.1.0"})
    assert check("0.0.1", ranges) == (True, "0.1.0")


def test_last_affected_is_inclusive_and_names_no_fix():
    ranges = semver({"introduced": "0"}, {"last_affected": "0.9.2"})
    assert check("0.9.2", ranges) == (True, "")
    assert check("0.9.3", ranges) == (False, "")


def test_a_range_never_closed_stays_open():
    ranges = semver({"introduced": "3.0.0"})
    assert check("99.0.0", ranges) == (True, "")
    assert check("2.9.9", ranges) == (False, "")


def test_missing_trailing_zeros_do_not_matter():
    ranges = semver({"introduced": "1.4"}, {"fixed": "1.5"})
    assert check("1.4.0", ranges) == (True, "1.5")
    assert check("1.5.0", ranges) == (False, "")


def test_a_version_can_be_hit_again_by_a_second_range():
    ranges = semver({"introduced": "1.0.0"}, {"fixed": "1.2.0"}, {"introduced": "2.0.0"}, {"fixed": "2.1.0"})
    assert check("1.5.0", ranges) == (False, "")
    assert check("2.0.5", ranges) == (True, "2.1.0")


def test_check_rejects_unsupported_types_and_mixed_events():
    with pytest.raises(ValueError):
        check("1.0.0", [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}]}])
    with pytest.raises(ValueError):
        check("1.0.0", semver({"introduced": "1.0.0", "fixed": "1.0.2"}))


def test_ecosystem_of():
    assert ecosystem_of("pkg:pypi/sandpay-json@1.4.0") == ("PyPI", "sandpay-json")
    assert ecosystem_of("pkg:npm/sandpay-widgets@3.2.0") == ("npm", "sandpay-widgets")
    assert ecosystem_of("pkg:pypi/sandpay-json") == ("PyPI", "sandpay-json")


@pytest.mark.parametrize("purl", ["", "sandpay-json", "pkg:maven/com.example/lib@1.0.0", "https://example.test/x"])
def test_ecosystem_of_rejects_what_it_cannot_read(purl):
    with pytest.raises(ValueError):
        ecosystem_of(purl)


def test_findings_for_the_fixture():
    found = find_findings(parse_cyclonedx(fx.CYCLONEDX_BOM), fx.ADVISORIES)
    assert found == [
        Finding("SPSA-2026-0001", "sandpay-json", "1.4.0", "1.4.2", 9.1),
        Finding("SPSA-2026-0003", "sandpay-crypto", "0.9.2", "", 5.9),
        Finding("SPSA-2026-0004", "sandpay-widgets-core", "1.0.3", "1.0.10", 6.1),
        Finding("SPSA-2026-0007", "sandpay-idna", "2.9.0", "2.10.0", 3.7),
    ]


def test_same_name_in_another_ecosystem_is_not_a_match():
    found = find_findings(parse_cyclonedx(fx.CYCLONEDX_BOM), fx.ADVISORIES)
    assert "SPSA-2026-0006" not in [f.advisory_id for f in found]


def test_a_component_without_a_purl_cannot_be_matched():
    adv = [{"id": "X-1", "affected": [{"package": {"ecosystem": "PyPI", "name": "lib"},
                                       "ranges": semver({"introduced": "0"})}],
            "database_specific": {"cvss_v4_score": 8.0}}]
    assert find_findings([Component("lib", "1.0.0", "", "Acme")], adv) == []
    assert find_findings([Component("lib", "1.0.0", "pkg:maven/x/lib@1.0.0", "Acme")], adv) == []
    assert len(find_findings([Component("lib", "1.0.0", "pkg:pypi/lib@1.0.0", "Acme")], adv)) == 1


def test_a_duplicate_component_gives_one_finding():
    comp = Component("sandpay-json", "1.4.0", "pkg:pypi/sandpay-json@1.4.0", "SandPay Open Source")
    assert len(find_findings([comp, comp], fx.ADVISORIES)) == 1


@pytest.mark.parametrize("score, expected", [
    (0.0, "None"), (0.1, "Low"), (3.9, "Low"), (4.0, "Medium"), (6.9, "Medium"),
    (7.0, "High"), (8.9, "High"), (9.0, "Critical"), (10.0, "Critical"),
])
def test_rating_follows_the_cvss_v4_scale(score, expected):
    assert rating(score) == expected


@pytest.mark.parametrize("score", [-0.1, 10.1])
def test_rating_rejects_scores_outside_the_scale(score):
    with pytest.raises(ValueError):
        rating(score)


@pytest.mark.parametrize("score, kev, epss, expected", [
    (2.0, True, 0.0, "P1"),      # exploited in the wild beats a low score
    (2.0, False, 0.5, "P1"),     # EPSS at the threshold
    (9.8, False, 0.49, "P2"),    # critical but not likely to be exploited
    (7.0, False, 0.0, "P2"),
    (6.9, False, 0.1, "P3"),
    (4.0, False, 0.0, "P3"),
    (3.9, False, 0.0, "P4"),
    (0.0, False, 0.0, "P4"),
])
def test_priority_policy(score, kev, epss, expected):
    assert priority(score, kev, epss) == expected


def test_triage_for_the_fixture():
    found = find_findings(parse_cyclonedx(fx.CYCLONEDX_BOM), fx.ADVISORIES)
    assert triage(found, fx.KNOWN_EXPLOITED, fx.EPSS) == [
        ("P1", "SPSA-2026-0003", "sandpay-crypto"),
        ("P2", "SPSA-2026-0001", "sandpay-json"),
        ("P3", "SPSA-2026-0004", "sandpay-widgets-core"),
        ("P4", "SPSA-2026-0007", "sandpay-idna"),
    ]


def test_triage_treats_missing_epss_as_zero_and_sorts_by_priority_then_id():
    findings = [Finding("B-2", "b", "1.0.0", "", 9.5), Finding("A-1", "a", "1.0.0", "", 9.5),
                Finding("C-3", "c", "1.0.0", "", 1.0)]
    assert triage(findings, {"C-3"}, {}) == [("P1", "C-3", "c"), ("P2", "A-1", "a"), ("P2", "B-2", "b")]
