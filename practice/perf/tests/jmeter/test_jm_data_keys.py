"""Exercise: jm_data_payments.jmx + jm_data_keys.py - a fresh Idempotency-Key per request, proved from the results."""

import re
from pathlib import Path

import pytest
from jmeter.jm_data_keys import key_report, payment_samples
from load_tools import jmeter_home, practice_file, run_jmeter
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

needs_jmeter = pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")
XML_HEADERS = {"jmeter.save.saveservice.output_format": "xml",
               "jmeter.save.saveservice.requestHeaders": "true",
               "jmeter.save.saveservice.responseHeaders": "true"}
REUSED = Path(__file__).parent / "fixtures" / "jm_data_reused_key.jmx"
THREADS, LOOPS = 3, 3


def sample(lb, rc, tn, key=None, replayed=False, request_headers=True):
    req = f"<requestHeader class=\"java.lang.String\">Content-Type: application/json\n" \
          f"{'Idempotency-Key: ' + key if key else ''}\n</requestHeader>" if request_headers else ""
    resp = f"<responseHeader class=\"java.lang.String\">HTTP/1.1 {rc} X\n" \
           f"{'Idempotent-Replayed: true' if replayed else ''}\n</responseHeader>"
    return f'<httpSample t="5" s="true" lb="{lb}" rc="{rc}" tn="{tn}">{resp}{req}</httpSample>'


def write(tmp_path, *samples):
    path = tmp_path / "r.jtl"
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<testResults version="1.2">\n' + "\n".join(samples)
                    + "\n</testResults>\n")
    return path


def test_payment_samples_reads_key_and_replay_flag(tmp_path):
    path = write(tmp_path, sample("POST /auth/token", "200", "M 1-1"),
                 sample("POST /v1/payments", "201", "M 1-1", key="k-1"),
                 sample("POST /v1/payments", "201", "M 1-1", key="k-1", replayed=True),
                 sample("POST /v1/payments", "400", "M 1-2"))
    assert payment_samples(path) == [
        {"thread": "M 1-1", "code": "201", "key": "k-1", "replayed": False},
        {"thread": "M 1-1", "code": "201", "key": "k-1", "replayed": True},
        {"thread": "M 1-2", "code": "400", "key": None, "replayed": False},
    ]


def test_payment_samples_refuses_a_file_without_request_headers(tmp_path):
    path = write(tmp_path, sample("POST /v1/payments", "201", "M 1-1", request_headers=False))
    with pytest.raises(ValueError):
        payment_samples(path)


def test_key_report_counts_duplicates_replays_and_real_payments():
    samples = [{"thread": "a", "code": "201", "key": "k-1", "replayed": False},
               {"thread": "a", "code": "201", "key": "k-1", "replayed": True},
               {"thread": "b", "code": "201", "key": "k-2", "replayed": False},
               {"thread": "b", "code": "400", "key": None, "replayed": False}]
    assert key_report(samples) == {"requests": 4, "unique_keys": 2, "missing_keys": 1, "duplicates": {"k-1": 2},
                                   "replayed": 1, "created": 2}


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    out = tmp_path_factory.mktemp("jm_data_keys")
    props = {"threads": THREADS, "loops": LOOPS, **XML_HEADERS}
    with serve(TargetConfig(latency_ms=1)) as base:
        props["port"] = base.rsplit(":", 1)[1]
        mine = run_jmeter(practice_file("jmeter/jm_data_payments.jmx"), props, out / "mine")
        reused = run_jmeter(REUSED, props, out / "reused")
    return mine, reused


@needs_jmeter
def test_your_plan_creates_every_payment(runs):
    text = runs[0].read_text()
    keys = re.findall(r"^Idempotency-Key: (.+)$", text, re.M)
    assert len(keys) == THREADS * LOOPS, "every payment request must send an Idempotency-Key"
    assert len(set(keys)) == len(keys), f"keys repeat: {sorted(keys)}"
    assert "Idempotent-Replayed: true" not in text


@needs_jmeter
def test_the_report_catches_a_key_reused_per_thread(runs):
    report = key_report(payment_samples(runs[1]))
    assert report["requests"] == THREADS * LOOPS
    assert report["replayed"] == THREADS * (LOOPS - 1)
    assert report["created"] == THREADS
    assert report["duplicates"] == {f"order-{t}": LOOPS for t in range(1, THREADS + 1)}
