"""Checks the .jmx auditor in exercises/jmeter/jm_http_audit.py against small plans built here, each with one
mistake, and against real plans from this project. No JMeter run is needed: the auditor reads the XML."""

from pathlib import Path

import pytest
from jmeter.jm_http_audit import audit, effective, plan_scopes

pytestmark = pytest.mark.exercise

ROOT = Path(__file__).resolve().parents[2]

DEFAULTS = """<ConfigTestElement guiclass="HttpDefaultsGui" testclass="ConfigTestElement" testname="HTTP Request Defaults">
  <stringProp name="HTTPSampler.domain">127.0.0.1</stringProp>
  <stringProp name="HTTPSampler.port">${__P(port,8090)}</stringProp>
  <stringProp name="HTTPSampler.connect_timeout">2000</stringProp>
  <stringProp name="HTTPSampler.response_timeout">5000</stringProp>
  IMPL
</ConfigTestElement><hashTree/>"""
JSON_HEADERS = """<HeaderManager guiclass="HeaderPanel" testclass="HeaderManager" testname="JSON">
  <collectionProp name="HeaderManager.headers"><elementProp name="" elementType="Header">
    <stringProp name="Header.name">Content-Type</stringProp><stringProp name="Header.value">application/json</stringProp>
  </elementProp></collectionProp></HeaderManager><hashTree/>"""
COOKIES = """<CookieManager guiclass="CookiePanel" testclass="CookieManager" testname="Cookies NAME">
  <collectionProp name="CookieManager.cookies"/></CookieManager><hashTree/>"""


def sampler(name="GET /v1/payments", method="GET", extra="", body="", children=""):
    args = ""
    if body:
        args = f"""<boolProp name="HTTPSampler.postBodyRaw">true</boolProp>
  <elementProp name="HTTPsampler.Arguments" elementType="Arguments"><collectionProp name="Arguments.arguments">
    <elementProp name="" elementType="HTTPArgument"><stringProp name="Argument.value">{body}</stringProp></elementProp>
  </collectionProp></elementProp>"""
    return f"""<HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="{name}">
  {args}<stringProp name="HTTPSampler.path">/v1/payments</stringProp>
  <stringProp name="HTTPSampler.method">{method}</stringProp>{extra}
</HTTPSamplerProxy><hashTree>{children}</hashTree>"""


def plan(tmp_path, *, top="", group="", samplers="", defaults=True, impl=""):
    d = DEFAULTS.replace("IMPL", impl) if defaults else ""
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3"><hashTree>
<TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="t"/><hashTree>
{d}{top}
<ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="Merchants"/><hashTree>
{group}{samplers}
</hashTree></hashTree></hashTree></jmeterTestPlan>"""
    path = tmp_path / "plan.jmx"
    path.write_text(xml)
    return path


def rules(path):
    return sorted((f.rule, f.element) for f in audit(path))


def test_a_clean_plan_has_no_findings(tmp_path):
    assert audit(plan(tmp_path, top=JSON_HEADERS, samplers=sampler() + sampler("POST /v1/payments", "POST",
                                                                                 body='{"amount_minor": 1}'))) == []


def test_no_defaults_is_one_plan_finding_and_missing_timeouts_per_sampler(tmp_path):
    found = rules(plan(tmp_path, defaults=False, samplers=sampler()))
    assert ("no-defaults", "plan") in found
    assert found.count(("no-timeouts", "GET /v1/payments")) == 2  # connect and response


def test_hard_coded_host_but_not_a_property(tmp_path):
    hard = '<stringProp name="HTTPSampler.domain">api.sandpay.example</stringProp>'
    prop = '<stringProp name="HTTPSampler.domain">${__P(host,127.0.0.1)}</stringProp>'
    assert rules(plan(tmp_path, samplers=sampler(extra=hard))) == [("hard-coded-host", "GET /v1/payments")]
    assert rules(plan(tmp_path, samplers=sampler(extra=prop))) == []


def test_sampler_timeout_overrides_missing_defaults(tmp_path):
    own = ('<stringProp name="HTTPSampler.connect_timeout">1000</stringProp>'
           '<stringProp name="HTTPSampler.response_timeout">3000</stringProp>')
    path = plan(tmp_path, defaults=False, samplers=sampler(extra=own))
    assert rules(path) == [("no-defaults", "plan")]
    _, scopes = plan_scopes(path)
    assert effective(scopes[0], "HTTPSampler.response_timeout") == "3000"


def test_effective_takes_the_defaults_value_when_the_sampler_is_empty(tmp_path):
    empty = '<stringProp name="HTTPSampler.response_timeout"></stringProp>'
    _, scopes = plan_scopes(plan(tmp_path, samplers=sampler(extra=empty)))
    assert effective(scopes[0], "HTTPSampler.response_timeout") == "5000"
    assert effective(scopes[0], "HTTPSampler.implementation") == ""


def test_java_implementation_from_defaults(tmp_path):
    java = '<stringProp name="HTTPSampler.implementation">Java</stringProp>'
    assert rules(plan(tmp_path, impl=java, samplers=sampler())) == [("java-implementation", "GET /v1/payments")]


def test_keepalive_off_auto_redirect_on_post_and_embedded_resources(tmp_path):
    off = '<boolProp name="HTTPSampler.use_keepalive">false</boolProp>'
    auto = '<boolProp name="HTTPSampler.auto_redirects">true</boolProp>'
    embedded = '<boolProp name="HTTPSampler.image_parser">true</boolProp>'
    found = rules(plan(tmp_path, top=JSON_HEADERS, samplers=sampler("a", extra=off)
                       + sampler("b", "POST", extra=auto, body="{}") + sampler("c", "GET", extra=auto)
                       + sampler("d", extra=embedded)))
    assert found == [("auto-redirect-on-post", "b"), ("embedded-resources", "d"), ("keepalive-off", "a")]


def test_content_type_must_be_in_scope_of_the_sampler(tmp_path):
    post = sampler("POST /v1/payments", "POST", body='{"amount_minor": 1}')
    # A Header Manager that is a child of ANOTHER sampler does not apply to this one.
    other = sampler("GET /v1/payments", children=JSON_HEADERS)
    assert rules(plan(tmp_path, samplers=other + post)) == [("missing-content-type", "POST /v1/payments")]
    # Its own child, or one in the thread group, does.
    assert rules(plan(tmp_path, samplers=sampler("POST /v1/payments", "POST", body="{}", children=JSON_HEADERS))) == []
    assert rules(plan(tmp_path, group=JSON_HEADERS, samplers=post)) == []
    # A POST without a body needs no Content-Type.
    assert rules(plan(tmp_path, samplers=sampler("POST /v1/refresh", "POST"))) == []


def test_disabled_elements_do_not_count(tmp_path):
    disabled = JSON_HEADERS.replace('testname="JSON"', 'testname="JSON" enabled="false"')
    assert rules(plan(tmp_path, group=disabled, samplers=sampler("p", "POST", body="{}"))) == [
        ("missing-content-type", "p")]


def test_several_cookie_managers_in_scope(tmp_path):
    two = COOKIES.replace("NAME", "1") + COOKIES.replace("NAME", "2")
    assert rules(plan(tmp_path, top=COOKIES.replace("NAME", "plan"), samplers=sampler())) == []
    assert rules(plan(tmp_path, group=two, samplers=sampler())) == [("several-cookie-managers", "GET /v1/payments")]


def test_the_reference_payment_plan_is_clean():
    assert audit(ROOT / "solutions" / "jmeter" / "jm_http_payment.jmx") == []


def test_the_connection_plan_with_keepalive_off(tmp_path):
    text = (ROOT / "tests" / "jmeter" / "fixtures" / "jm_http_conn.jmx").read_text().replace("KEEPALIVE", "false")
    path = tmp_path / "conn.jmx"
    path.write_text(text)
    assert {f.rule for f in audit(path)} == {"keepalive-off"}
    assert len(audit(path)) == 3
