"""jm_logic_ exercise 2: run a step only when the previous one worked (exercises/jmeter/jm_logic_created.jmx).

Runs the plan once with real JMeter against support/jm_logic_fixture.py: 3 threads x 8 iterations = 24
payments, of which every 4th (6 in all) is a 500 with no id - exact on any machine.
"""

import xml.etree.ElementTree as ET
from collections import Counter

import pytest
from jm_logic_fixture import metrics, serve
from load_tools import jmeter_home, practice_file, read_jtl, run_jmeter

pytestmark = pytest.mark.exercise

PLAN = practice_file("jmeter/jm_logic_created.jmx")
FETCH = "GET /v1/payments/{id}"


def prop(el: ET.Element, name: str) -> str:
    for child in el:
        if child.get("name") == name:
            return (child.text or "").strip()
    return ""


def if_controllers_around_fetch(root: ET.Element) -> list[ET.Element]:
    found = []
    for tree in root.iter("hashTree"):
        items = list(tree)
        for i, el in enumerate(items):
            if el.tag == "IfController" and el.get("enabled", "true") == "true":
                if any(s.get("testname") == FETCH for s in items[i + 1].iter("HTTPSamplerProxy")):
                    found.append(el)
    return found


def test_the_look_up_is_inside_an_if_controller_in_expression_mode():
    found = if_controllers_around_fetch(ET.parse(PLAN).getroot())
    assert len(found) == 1, f"wrap {FETCH} in one If Controller"
    ifc = found[0]
    assert prop(ifc, "IfController.useExpression") == "true", (
        "tick 'Interpret Condition as Variable Expression?' - the JavaScript mode is the slow one")
    condition = prop(ifc, "IfController.condition")
    assert "__jexl3(" in condition or "__groovy(" in condition, "write the condition with __jexl3 or __groovy"
    assert "payment_id" in condition


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("jm_logic_created")
    with serve() as base:
        props = {"port": base.rsplit(":", 1)[1], "threads": 3, "loops": 8}
        rows = read_jtl(run_jmeter(PLAN, props, out))
        return rows, metrics(base)


@pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")
def test_only_created_payments_are_looked_up(run):
    rows, server = run
    codes = Counter((r["label"], r["responseCode"]) for r in rows)
    assert codes[("POST /v1/payments", "201")] == 18 and codes[("POST /v1/payments", "500")] == 6
    assert codes[(FETCH, "404")] == 0, "the plan asked for a payment that was never created"
    assert codes[(FETCH, "200")] == 18
    assert server["routes"].get("GET /v1/payments/<id>") == 18


@pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")
def test_failed_checkouts_contain_only_the_failed_payment(run):
    rows, _ = run
    failed = [r for r in rows if r["label"] == "Checkout" and r["success"] == "false"]
    assert len(failed) == 6
    assert {r["responseMessage"] for r in failed} == {
        "Number of samples in transaction : 1, number of failing samples : 1"}
