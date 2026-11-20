"""jm_groovy_ exercise 1: fix the Groovy pre-processor and add a Groovy assertion in jm_groovy_sign.jmx.

Runs the plan once with real JMeter against support/jm_groovy_fixture.py, which accepts a payment only with a
valid HMAC signature and counts replays of an Idempotency-Key. 2 threads x 6 loops with unique keys create
exactly 12 payments, and the fixture's counter declines exactly 3 of them (the 4th, 8th and 12th).
"""

import xml.etree.ElementTree as ET
from collections import Counter

import pytest
from jm_groovy_fixture import serve
from load_tools import jmeter_home, practice_file, read_jtl, run_jmeter

pytestmark = [pytest.mark.exercise,
              pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")]

PLAN = practice_file("jmeter/jm_groovy_sign.jmx")
THREADS, LOOPS = 2, 6
TOKEN, CREATE = "POST /auth/token", "POST /v1/payments"


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("jm_groovy_sign")
    with serve() as target:
        props = {"port": target.port, "threads": THREADS, "loops": LOOPS,
                 "jmeter.save.saveservice.timestamp_format": "HH:mm:ss.SSS"}
        rows = read_jtl(run_jmeter(PLAN, props, out))
        return rows, target.stats()


def jsr223_elements():
    root = ET.parse(PLAN).getroot()
    return [el for el in root.iter() if el.tag.startswith("JSR223")]


def test_every_sampler_ran(run):
    rows, _ = run
    assert Counter(r["label"] for r in rows) == {TOKEN: THREADS, CREATE: THREADS * LOOPS}


def test_every_signature_is_accepted(run):
    rows, stats = run
    assert stats["bad_signature"] == 0, "the server rejected a signature - check the message <ts>.<key>.<body>"
    assert {r["responseCode"] for r in rows if r["label"] == CREATE} == {"201"}


def test_every_request_creates_a_new_payment(run):
    _, stats = run
    assert stats["replays"] == 0, (
        f"{stats['replays']} requests replayed an earlier Idempotency-Key {stats['keys']} - "
        "a cached script keeps the first value of every ${...} it contains"
    )
    assert stats["created"] == THREADS * LOOPS and len(stats["keys"]) == THREADS * LOOPS


def test_declined_payments_fail_on_the_groovy_assertion(run):
    rows, _ = run
    failed = [r for r in rows if r["label"] == CREATE and r["success"] == "false"]
    assert len(failed) == 3, "the 4th, 8th and 12th new payments are declined - the assertion must fail exactly those"
    for r in failed:
        assert "declined" in r["failureMessage"] and "pay_" in r["failureMessage"], r["failureMessage"]


def test_scripts_are_groovy_cached_and_free_of_interpolation():
    elements = jsr223_elements()
    tags = {el.tag for el in elements}
    assert {"JSR223PreProcessor", "JSR223Assertion"} <= tags, f"found only {sorted(tags)}"
    for el in elements:
        name = el.get("testname")
        assert el.findtext("stringProp[@name='scriptLanguage']") == "groovy", name
        assert (el.findtext("stringProp[@name='cacheKey']") or "false") != "false", f"{name}: cache is off"
        assert "${" not in (el.findtext("stringProp[@name='script']") or ""), f"{name}: ${{...}} inside a cached script"
