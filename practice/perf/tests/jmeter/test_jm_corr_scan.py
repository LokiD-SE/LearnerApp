from pathlib import Path

import pytest
from jmeter.jm_corr_scan import defined_variables, scan
from load_tools import practice_file

pytestmark = pytest.mark.exercise

RECORDED = (Path(__file__).parent / "fixtures" / "jm_corr_recorded.jmx").read_text()
ROOT = Path(__file__).resolve().parents[2]


def plan(body: str) -> str:
    return f'<jmeterTestPlan version="1.2"><hashTree><TestPlan testname="t"/><hashTree>{body}</hashTree></hashTree></jmeterTestPlan>'


def test_recorded_plan_findings():
    assert scan(RECORDED) == [
        ("hardcoded-id", "GET /v1/payments page 2", "pay_100005"),
        ("hardcoded-id", "GET /v1/payments/{id}", "pay_100003"),
        ("hardcoded-token", "Recorded headers", "Authorization: Bearer rec0rdedT0kenFromTuesday"),
        ("never-set", "Recorded headers", "trace_id"),
        ("no-default", "token (regex)", "token"),
    ]


def test_defined_variables_cover_extractors_udv_and_csv():
    import xml.etree.ElementTree as ET

    assert defined_variables(ET.fromstring(RECORDED)) == {"client_id", "client_secret", "token"}
    solution = (ROOT / "solutions" / "jmeter" / "jm_corr_paging.jmx").read_text()
    assert {"after", "token", "has_more", "page_id"} <= defined_variables(ET.fromstring(solution))


def test_the_correlated_solution_plan_is_clean():
    assert scan((ROOT / "solutions" / "jmeter" / "jm_corr_paging.jmx").read_text()) == []


def test_functions_are_not_variables():
    body = """<HTTPSamplerProxy testname="s"><stringProp name="HTTPSampler.path">/v1/payments?limit=${__P(limit,5)}&amp;u=${__threadNum}</stringProp></HTTPSamplerProxy>"""
    assert scan(plan(body)) == []


def test_authorization_with_a_variable_is_fine_but_unset_variable_is_reported():
    body = """<HeaderManager testname="h"><collectionProp name="HeaderManager.headers">
      <elementProp name="" elementType="Header"><stringProp name="Header.name">authorization</stringProp>
      <stringProp name="Header.value">Bearer ${tok}</stringProp></elementProp></collectionProp></HeaderManager>"""
    assert scan(plan(body)) == [("never-set", "h", "tok")]


def test_json_extractor_defaults_must_cover_every_variable():
    body = """<JSONPostProcessor testname="two vars">
      <stringProp name="JSONPostProcessor.referenceNames">a;b</stringProp>
      <stringProp name="JSONPostProcessor.jsonPathExprs">$.a;$.b</stringProp>
      <stringProp name="JSONPostProcessor.defaultValues">A_NOT_FOUND</stringProp></JSONPostProcessor>
      <BoundaryExtractor testname="boundary ok">
      <stringProp name="BoundaryExtractor.refname">c</stringProp>
      <stringProp name="BoundaryExtractor.default">C_NOT_FOUND</stringProp></BoundaryExtractor>"""
    assert scan(plan(body)) == [("no-default", "two vars", "a;b")]


def test_the_learners_paging_plan_scans_clean_once_correlated():
    # Fails until the exercise plan sets ${token} with an extractor (and every extractor has a default).
    assert scan(practice_file("jmeter/jm_corr_paging.jmx").read_text()) == []
