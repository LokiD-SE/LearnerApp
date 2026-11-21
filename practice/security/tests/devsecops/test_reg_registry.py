"""Checks exercises/devsecops/reg_registry.py: parse a finding-to-test registry and report what is wrong with it."""

import json

import pytest
from devsecops.reg_registry import coverage, parse_collected, parse_registry, registry_problems
from reg_fixture import COLLECT_OUTPUT, SAMPLE_REGISTRY, Entry, Problem

pytestmark = pytest.mark.exercise

TODAY = "2026-11-21"
TEST_101 = "tests/regression/test_sp101_idor.py::test_alice_cannot_read_bobs_payment"


def entry(**overrides):
    base = {"id": "SP-1", "flaw": "idor", "severity": "High", "status": "open"}
    return json.dumps([{**base, **overrides}])


def test_parse_registry_reads_every_entry_and_its_optional_fields():
    entries = parse_registry(SAMPLE_REGISTRY)
    assert [e.id for e in entries] == [f"SP-10{i}" for i in range(1, 8)]
    first = entries[0]
    assert isinstance(first, Entry)
    assert (first.flaw, first.severity, first.status, first.fixed_in, first.test) == (
        "idor", "High", "fixed", "build-412", TEST_101)
    assert entries[2].test is None
    assert (entries[5].accepted_until, entries[5].reason) == ("2026-10-31", "password rehash planned for the next release")
    assert entries[6].accepted_until is None and entries[6].reason is None


@pytest.mark.parametrize("text, why", [
    ("not json", "invalid JSON"),
    ('{"id": "SP-1"}', "not a list"),
    ("[1]", "entry is not an object"),
    ('[{"id": "SP-1", "flaw": "idor", "severity": "High"}]', "missing status"),
    ('[{"flaw": "idor", "severity": "High", "status": "open"}]', "missing id"),
    (entry(status="wontfix"), "unknown status"),
    (entry(severity="Severe"), "unknown severity"),
    (json.dumps([json.loads(entry())[0], json.loads(entry())[0]]), "duplicate id"),
])
def test_parse_registry_fails_closed(text, why):
    with pytest.raises(ValueError):
        parse_registry(text)


def test_parse_collected_keeps_only_node_ids():
    ids = parse_collected(COLLECT_OUTPUT)
    assert ids == {
        TEST_101,
        "tests/regression/test_sp102_redirect.py::test_login_next_stays_on_site",
        "tests/regression/test_sp105_xss.py::test_search_encodes_output",
        "tests/regression/test_old_cors.py::test_cors_wildcard",
    }


def test_parse_collected_ignores_summaries_warnings_and_blank_lines():
    text = "\n  tests/a.py::test_one  \n\n1 test collected in 0.01s\nwarning: something::odd happened\n"
    assert parse_collected(text) == {"tests/a.py::test_one"}
    assert parse_collected("") == set()


def test_the_sample_registry_has_exactly_the_documented_problems():
    problems = registry_problems(parse_registry(SAMPLE_REGISTRY), parse_collected(COLLECT_OUTPUT), TODAY)
    assert all(isinstance(p, Problem) for p in problems)
    assert [(p.kind, p.finding_id) for p in problems] == [
        ("fixed-without-test", "SP-103"),
        ("dangling-test", "SP-104"),
        ("accepted-expired", "SP-106"),
        ("accepted-incomplete", "SP-107"),
        ("orphan-test", None),
    ]
    assert "test_old_cors" in problems[-1].detail
    assert "test_sp104_sqli" in problems[1].detail


def test_a_healthy_registry_has_no_problems():
    text = entry(status="fixed", test="tests/a.py::test_one")
    assert registry_problems(parse_registry(text), {"tests/a.py::test_one"}, TODAY) == []


def test_an_open_finding_may_have_no_test_yet():
    assert registry_problems(parse_registry(entry()), set(), TODAY) == []


def test_an_open_finding_that_names_a_missing_test_is_dangling():
    problems = registry_problems(parse_registry(entry(test="tests/a.py::test_gone")), set(), TODAY)
    assert [(p.kind, p.finding_id) for p in problems] == [("dangling-test", "SP-1")]


def test_acceptance_ends_the_day_after_the_date_not_on_it():
    on_the_day = entry(status="accepted", accepted_until=TODAY, reason="vendor patch due")
    assert registry_problems(parse_registry(on_the_day), set(), TODAY) == []
    day_before = entry(status="accepted", accepted_until="2026-11-20", reason="vendor patch due")
    assert [p.kind for p in registry_problems(parse_registry(day_before), set(), TODAY)] == ["accepted-expired"]


def test_an_accepted_risk_needs_both_a_date_and_a_reason():
    no_reason = entry(status="accepted", accepted_until="2027-01-31")
    no_date = entry(status="accepted", reason="vendor patch due")
    for text in (no_reason, no_date):
        assert [p.kind for p in registry_problems(parse_registry(text), set(), TODAY)] == ["accepted-incomplete"]


def test_orphan_tests_are_sorted_and_have_no_finding_id():
    problems = registry_problems([], {"tests/b.py::t", "tests/a.py::t"}, TODAY)
    assert [(p.kind, p.finding_id) for p in problems] == [("orphan-test", None)] * 2
    assert "tests/a.py::t" in problems[0].detail and "tests/b.py::t" in problems[1].detail


def test_coverage_counts_fixed_findings_with_a_collected_test():
    entries = parse_registry(SAMPLE_REGISTRY)
    assert coverage(entries, parse_collected(COLLECT_OUTPUT)) == {"fixed": 4, "covered": 2, "ratio": 0.5}


def test_coverage_of_a_registry_with_nothing_fixed_is_complete():
    assert coverage(parse_registry(entry()), set()) == {"fixed": 0, "covered": 0, "ratio": 1.0}
    assert coverage([], set())["ratio"] == 1.0
