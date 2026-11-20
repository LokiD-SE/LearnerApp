"""Exercise: complete the SandPay smoke plan (exercises/jmeter/jm_arch_plan.jmx) and run it with JMeter."""

import json
import urllib.request
import xml.etree.ElementTree as ET

import pytest
from load_tools import jmeter_home, practice_file, read_jtl, run_jmeter
from sandpay_target import TargetConfig, serve

pytestmark = [
    pytest.mark.exercise,
    pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)"),
]

PLAN = practice_file("jmeter/jm_arch_plan.jmx")
THREADS, LOOPS = 2, 3


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("jm_arch_plan")
    with serve(TargetConfig(latency_ms=2)) as base:
        port = base.rsplit(":", 1)[1]
        rows = read_jtl(run_jmeter(PLAN, {"port": port, "threads": THREADS, "loops": LOOPS}, out))
        with urllib.request.urlopen(base + "/metrics") as r:
            metrics = json.load(r)
    return rows, metrics


def test_signs_in_once_per_thread(run):
    rows, metrics = run
    assert sum(r["label"] == "POST /auth/token" for r in rows) == THREADS
    assert metrics["routes"].get("POST /auth/token") == THREADS


def test_lists_payments_every_iteration_with_the_token(run):
    rows, _ = run
    lists = [r for r in rows if r["label"] == "GET /v1/payments"]
    assert len(lists) == THREADS * LOOPS
    codes = sorted({r["responseCode"] for r in lists})
    assert codes == ["200"], f"GET /v1/payments answered {codes} - is the bearer token extracted and sent?"
    assert all(r["success"] == "true" for r in rows)


def test_extractor_is_a_child_of_the_sign_in_sampler():
    # Each element is followed by the <hashTree> holding its children, so the extractor's sampler is the
    # element just before the hashTree that contains it.
    root = ET.parse(PLAN).getroot()
    found = []
    for tree in root.iter("hashTree"):
        items = list(tree)
        for i, item in enumerate(items):
            if item.tag == "hashTree" and i > 0:
                owner = items[i - 1]
                for child in item:
                    if child.tag == "JSONPostProcessor" and child.get("enabled", "true") != "false":
                        found.append(owner.get("testname"))
    assert found == ["POST /auth/token"], f"JSON extractors found under: {found}"


def test_samplers_leave_the_server_to_http_request_defaults():
    root = ET.parse(PLAN).getroot()
    for sampler in root.iter("HTTPSamplerProxy"):
        domain = sampler.find("stringProp[@name='HTTPSampler.domain']")
        assert domain is None or not (domain.text or "").strip(), f"{sampler.get('testname')} hard-codes a domain"
