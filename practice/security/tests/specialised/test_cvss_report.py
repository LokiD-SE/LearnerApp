"""Checks exercises/specialised/cvss_report.py: the qualitative rating and the finding linter."""

import copy

import pytest
import cvss_fixture as fx
from specialised.cvss_report import lint_finding, qualitative

pytestmark = pytest.mark.exercise


def lint(finding):
    return lint_finding(finding, fx.stub_score_of)


def changed(**edits):
    """A copy of the good finding with top-level fields replaced (a value of None removes the field)."""
    finding = copy.deepcopy(fx.GOOD_FINDING)
    for key, value in edits.items():
        if value is None:
            finding.pop(key, None)
        else:
            finding[key] = value
    return finding


@pytest.mark.parametrize("score, rating", [
    (0.0, "None"), (0.1, "Low"), (3.9, "Low"), (4.0, "Medium"), (6.9, "Medium"),
    (7.0, "High"), (8.9, "High"), (9.0, "Critical"), (10.0, "Critical"),
])
def test_the_qualitative_severity_rating_scale(score, rating):
    assert qualitative(score) == rating


def test_a_complete_finding_has_no_problems():
    assert lint(fx.GOOD_FINDING) == []


def test_each_required_field_is_reported_when_it_is_missing_or_empty():
    for field in ("title", "affected", "cwe", "cvss", "summary", "steps", "evidence", "impact", "remediation"):
        assert lint(changed(**{field: None})) == [f"missing:{field}"], field
    assert lint(changed(steps=[])) == ["missing:steps"]
    assert lint(changed(title="")) == ["missing:title"]


@pytest.mark.parametrize("cwe", ["639", "CWE639", "cwe-639", "CWE-0", "CWE-1234567", "CWE-639 (IDOR)"])
def test_a_cwe_must_look_like_cwe_dash_number(cwe):
    assert lint(changed(cwe=cwe)) == ["bad-cwe"]


def test_a_cve_is_optional_but_must_be_well_formed_when_present():
    assert lint(changed(cve="CVE-2026-1234")) == []
    for bad in ("CVE-26-1234", "cve-2026-1234", "CVE-2026-12", "2026-1234"):
        assert lint(changed(cve=bad)) == ["bad-cve"], bad


def test_the_score_must_match_the_vector_and_the_rating_must_match_the_score():
    good = fx.GOOD_FINDING["cvss"]
    assert lint(changed(cvss={**good, "score": 9.8})) == ["rating-mismatch", "score-mismatch"]
    assert lint(changed(cvss={**good, "rating": "Critical"})) == ["rating-mismatch"]
    assert lint(changed(cvss={**good, "score": 7.2})) == ["score-mismatch"]  # 7.2 is also High: only the score is wrong


def test_a_vector_the_scorer_rejects_is_reported_once_and_not_scored():
    good = fx.GOOD_FINDING["cvss"]
    assert lint(changed(cvss={**good, "vector": "CVSS:4.0/AV:N"})) == ["bad-vector"]
    assert lint(changed(cvss={**good, "vector": ""})) == ["bad-vector"]


def test_a_reader_must_be_able_to_repeat_it_in_two_or_more_steps():
    assert lint(changed(steps=["Open the app and look."])) == ["steps-too-few"]


def test_an_impact_of_a_few_words_is_not_an_impact_statement():
    assert lint(changed(impact="Critical")) == ["impact-too-thin"]
    assert lint(changed(impact="Data can be read by others.")) == ["impact-too-thin"]


def test_evidence_needs_a_request_and_a_response():
    assert lint(changed(evidence=[{"request": "GET /api/payments/pay_2001"}])) == ["evidence-incomplete"]
    assert lint(changed(evidence=[{"request": "", "response": "200 {}"}])) == ["evidence-incomplete"]


@pytest.mark.parametrize("request_text", [
    "GET /api/payments/pay_2001  Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.e30.abcdefghijk",
    'POST /api/login {"email": "alice@shop-a.example", "password": "alice-pass-1"}',
])
def test_a_live_secret_in_the_evidence_is_reported(request_text):
    evidence = [{"request": request_text, "response": "200 {}"}]
    assert lint(changed(evidence=evidence)) == ["secret-in-evidence"]


def test_a_redacted_secret_is_fine():
    evidence = [{"request": 'POST /api/login {"email": "a@x.example", "password": "[REDACTED]"}',
                 "response": "200 {}"}]
    assert lint(changed(evidence=evidence)) == []


def test_a_card_number_like_digit_run_in_the_evidence_is_reported():
    digits = "4" * 16  # synthetic
    evidence = [{"request": "GET /api/payments/pay_2001", "response": f"200 {{\"pan\": \"{digits}\"}}"}]
    assert lint(changed(evidence=evidence)) == ["card-number-in-evidence"]
    ok = [{"request": "GET /api/payments/pay_2001", "response": '200 {"card_last4": "4242", "amount_minor": 12000}'}]
    assert lint(changed(evidence=ok)) == []


def test_problems_are_sorted_and_not_repeated():
    problems = lint(changed(cwe="639", steps=["one"], impact="bad",
                            evidence=[{"request": "", "response": ""}, {"request": "", "response": ""}]))
    assert problems == sorted(set(problems))
    assert problems == ["bad-cwe", "evidence-incomplete", "impact-too-thin", "steps-too-few"]


def test_the_linter_does_not_change_the_finding():
    finding = copy.deepcopy(fx.GOOD_FINDING)
    lint(finding)
    assert finding == fx.GOOD_FINDING
