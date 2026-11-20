"""jm_logic_ exercise 1: shape a checkout journey with logic controllers (exercises/jmeter/jm_logic_journey.jmx).

The structure tests read the plan; the run test executes it once with real JMeter against
support/jm_logic_fixture.py, whose failures come from a request counter (every 4th payment is a 500), so the
counts are exact on any machine: 3 threads x 8 iterations, the report at 50% per user.
"""

import xml.etree.ElementTree as ET
from collections import Counter

import pytest
from jm_logic_fixture import metrics, serve
from load_tools import jmeter_home, practice_file, read_jtl, run_jmeter

pytestmark = pytest.mark.exercise

PLAN = practice_file("jmeter/jm_logic_journey.jmx")
TOKEN, CREATE, FETCH, REPORT = "POST /auth/token", "POST /v1/payments", "GET /v1/payments/{id}", "GET /v1/reports/settlement"


def children(root: ET.Element, element: ET.Element) -> ET.Element:
    """In a .jmx an element's children are in the hashTree that follows it."""
    for tree in root.iter("hashTree"):
        items = list(tree)
        for i, el in enumerate(items):
            if el is element:
                return items[i + 1]
    raise AssertionError(f"{element.tag} has no hashTree")


def enabled(root: ET.Element, tag: str) -> list[ET.Element]:
    return [e for e in root.iter(tag) if e.get("enabled", "true") == "true"]


def samplers_under(root: ET.Element, controller: ET.Element) -> set[str]:
    return {s.get("testname") for s in children(root, controller).iter("HTTPSamplerProxy")}


def prop(el: ET.Element, name: str) -> str:
    for child in el:
        if child.get("name") == name:
            return (child.text or "").strip()
    return ""


@pytest.fixture(scope="module")
def root():
    return ET.parse(PLAN).getroot()


def test_sign_in_is_inside_a_once_only_controller(root):
    found = [c for c in enabled(root, "OnceOnlyController") if TOKEN in samplers_under(root, c)]
    assert found, "wrap POST /auth/token in a Once Only Controller"
    assert samplers_under(root, found[0]) == {TOKEN}, "only the sign-in belongs in the Once Only Controller"


def test_checkout_transaction_wraps_payment_and_look_up(root):
    found = [c for c in enabled(root, "TransactionController") if c.get("testname") == "Checkout"]
    assert len(found) == 1, "add one Transaction Controller named Checkout"
    assert samplers_under(root, found[0]) == {CREATE, FETCH}
    assert prop(found[0], "TransactionController.parent") != "true", (
        "use the default mode: the transaction sample is added after its samples, which stay separate rows")


def test_report_is_in_a_per_user_percent_throughput_controller(root):
    found = [c for c in enabled(root, "ThroughputController") if REPORT in samplers_under(root, c)]
    assert len(found) == 1, "wrap GET /v1/reports/settlement in a Throughput Controller"
    tc = found[0]
    assert prop(tc, "ThroughputController.style") == "1", "style 1 is 'percent executions' (0 is total executions)"
    assert prop(tc, "ThroughputController.perThread") == "true", "check 'per user'"
    assert "__P(report_percent" in prop(tc, "ThroughputController.percentThroughput"), (
        "read the percentage from the report_percent property")


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("jm_logic_journey")
    with serve() as base:
        props = {"port": base.rsplit(":", 1)[1], "threads": 3, "loops": 8, "report_percent": 50}
        rows = read_jtl(run_jmeter(PLAN, props, out))
        return rows, metrics(base)


@pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")
def test_real_run_has_the_predicted_mix(run):
    rows, server = run
    assert Counter(r["label"] for r in rows) == {TOKEN: 3, CREATE: 24, FETCH: 24, "Checkout": 24, REPORT: 12}, (
        "per thread: 1 sign-in, 8 checkouts, and the report on 4 of 8 passes at 50%")
    assert server["routes"].get("POST /auth/token") == 3, "the server saw more sign-ins than threads"


@pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")
def test_a_checkout_fails_when_any_of_its_samples_fails(run):
    rows, _ = run
    checkout = [r for r in rows if r["label"] == "Checkout"]
    assert sum(r["success"] == "false" for r in checkout) == 6, "6 of 24 payments are 500s, so 6 checkouts fail"
    assert all(r["responseMessage"].startswith("Number of samples in transaction : 2") for r in checkout)
