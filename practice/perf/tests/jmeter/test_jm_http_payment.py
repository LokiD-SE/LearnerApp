"""Runs exercises/jmeter/jm_http_payment.jmx with real JMeter (non-GUI) against the practice API and checks what
JMeter actually sent: the results file is switched to XML with request headers saved (JMeter properties
jmeter.save.saveservice.*), so every request's headers and body can be inspected."""

import json
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter

import pytest
from load_tools import jmeter_home, practice_file, run_jmeter
from sandpay_target import TargetConfig, serve

pytestmark = [pytest.mark.exercise,
              pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")]

THREADS, LOOPS, MERCHANT = 2, 3, 7
PLAN = practice_file("jmeter/jm_http_payment.jmx")
SAVE = {"jmeter.save.saveservice.output_format": "xml", "jmeter.save.saveservice.requestHeaders": "true",
        "jmeter.save.saveservice.samplerData": "true",
        "jmeter.save.saveservice.response_data": "false"}


def headers_of(sample: ET.Element) -> dict[str, str]:
    lines = (sample.findtext("requestHeader") or "").splitlines()
    return {k.strip().lower(): v.strip() for k, _, v in (line.partition(":") for line in lines) if k}


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    with serve(TargetConfig(latency_ms=0)) as base:
        jtl = run_jmeter(PLAN, {"port": base.rsplit(":", 1)[1], "threads": THREADS, "loops": LOOPS,
                                "merchant": MERCHANT, **SAVE}, tmp_path_factory.mktemp("jmeter"))
        # What the API now holds for merchant-7 (no seeded payments): one per created payment.
        token_req = urllib.request.Request(base + "/auth/token", method="POST", data=json.dumps(
            {"client_id": f"merchant-{MERCHANT}", "client_secret": f"secret-{MERCHANT}"}).encode())
        token = json.load(urllib.request.urlopen(token_req))["access_token"]
        listing = urllib.request.Request(base + "/v1/payments?limit=100", headers={"Authorization": f"Bearer {token}"})
        stored = json.load(urllib.request.urlopen(listing))["data"]
    return list(ET.parse(jtl).getroot()), stored


def by_label(samples, label):
    return [s for s in samples if s.get("lb") == label]


def test_every_sample_succeeds(run):
    samples, _ = run
    failed = [(s.get("lb"), s.get("rc"), s.get("rm")) for s in samples if s.get("s") != "true"]
    assert samples and not failed, f"failed samples (first 3): {failed[:3]} - check HTTP Request Defaults"


def test_signs_in_once_per_thread_and_creates_a_payment_per_iteration(run):
    samples, _ = run
    labels = Counter(s.get("lb") for s in samples)
    assert labels["POST /auth/token"] == THREADS
    assert [s.get("rc") for s in by_label(samples, "POST /v1/payments")] == ["201"] * (THREADS * LOOPS)


def test_json_content_type_on_every_request(run):
    samples, _ = run
    for s in samples:
        assert headers_of(s).get("content-type") == "application/json", (s.get("lb"), headers_of(s))


def test_bearer_token_on_api_calls_only(run):
    samples, _ = run
    for s in by_label(samples, "POST /auth/token"):
        assert "authorization" not in headers_of(s), "the sign-in request must not send Authorization"
    for label in ("POST /v1/payments", "GET /v1/payments"):
        for s in by_label(samples, label):
            auth = headers_of(s).get("authorization", "")
            assert auth.startswith("Bearer ") and "${" not in auth and "NO_TOKEN" not in auth, (label, auth)


def test_unique_idempotency_key_per_payment(run):
    samples, stored = run
    keys = [headers_of(s).get("idempotency-key") for s in by_label(samples, "POST /v1/payments")]
    assert None not in keys, "POST /v1/payments needs an Idempotency-Key header"
    assert len(set(keys)) == len(keys), "every request needs a new key, or the API replays the first payment"
    for s in by_label(samples, "GET /v1/payments"):
        assert "idempotency-key" not in headers_of(s), "the key belongs to the POST only (a child Header Manager)"
    assert len(stored) == THREADS * LOOPS, f"the API holds {len(stored)} payments for merchant-{MERCHANT}"


def test_payment_body_is_the_json_document(run):
    samples, stored = run
    for s in by_label(samples, "POST /v1/payments"):
        assert json.loads(s.findtext("queryString") or "null") == {"amount_minor": 1250, "currency": "EUR"}
    assert {(p["amount_minor"], p["currency"]) for p in stored} == {(1250, "EUR")}


def test_server_and_timeouts_come_from_http_request_defaults():
    root = ET.parse(PLAN).getroot()
    defaults = [e for e in root.iter("ConfigTestElement") if e.get("guiclass") == "HttpDefaultsGui"]
    assert len(defaults) == 1, "add one HTTP Request Defaults element at plan level"
    props = {p.get("name"): (p.text or "") for p in defaults[0].iter("stringProp")}
    assert props.get("HTTPSampler.domain") == "127.0.0.1"
    assert "__P(port" in props.get("HTTPSampler.port", ""), "take the port from the port property: ${__P(port,8090)}"
    for name in ("HTTPSampler.connect_timeout", "HTTPSampler.response_timeout"):
        assert props.get(name, "").isdigit() and int(props[name]) > 0, f"set {name} in the defaults"
    for sampler in root.iter("HTTPSamplerProxy"):
        sprops = {p.get("name"): (p.text or "") for p in sampler.iter("stringProp")}
        assert not sprops.get("HTTPSampler.domain"), f"{sampler.get('testname')} hard-codes a server"
