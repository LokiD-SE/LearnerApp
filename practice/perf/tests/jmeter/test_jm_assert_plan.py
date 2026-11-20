"""jm_assert_ exercise 1: add assertions to exercises/jmeter/jm_assert_plan.jmx.

Runs the plan once with real JMeter against support/jm_assert_fixture.py, whose failures are deterministic:
2 threads x 10 loops give 20 samples per sampler, with 5 soft errors on GET /v1/payments, 4 x 500 and
2 x "declined" on POST /v1/payments, and a report that always takes about 150 ms.
"""

from collections import Counter

import pytest
from jm_assert_fixture import serve
from load_tools import practice_file, read_jtl, run_jmeter

pytestmark = pytest.mark.exercise

LIST, CREATE, REPORT, TOKEN = "GET /v1/payments", "POST /v1/payments", "GET /v1/reports/settlement", "POST /auth/token"


@pytest.fixture(scope="module")
def rows(tmp_path_factory):
    out = tmp_path_factory.mktemp("jm_assert_plan")
    with serve() as base:
        props = {"port": base.rsplit(":", 1)[1], "threads": 2, "loops": 10, "report_ms": 100,
                 "jmeter.save.saveservice.timestamp_format": "HH:mm:ss.SSS"}
        return read_jtl(run_jmeter(practice_file("jmeter/jm_assert_plan.jmx"), props, out))


def failed(rows, label):
    return [r for r in rows if r["label"] == label and r["success"] == "false"]


def test_every_sampler_ran(rows):
    assert Counter(r["label"] for r in rows) == {TOKEN: 2, LIST: 20, CREATE: 20, REPORT: 20}


def test_soft_errors_fail_on_the_json_assertion(rows):
    bad = failed(rows, LIST)
    assert len(bad) == 5, "a 200 with an error body must fail: assert that $.data exists"
    assert all("data" in r["failureMessage"] for r in bad), [r["failureMessage"] for r in bad]


def test_server_errors_carry_the_custom_message(rows):
    errors = [r for r in rows if r["label"] == CREATE and r["responseCode"] == "500"]
    assert len(errors) == 4
    assert all(r["success"] == "false" for r in errors)
    assert {r["failureMessage"] for r in errors} == {"payment not created: expected HTTP 201"}, (
        "a 500 is failed even without an assertion, but its failureMessage is empty - add the Response Assertion"
    )


def test_declined_payments_fail_on_the_status_value(rows):
    declined = [r for r in failed(rows, CREATE) if r["responseCode"] == "201"]
    assert len(declined) == 2, "a 201 whose $.status is not captured must fail"
    assert all("captured" in r["failureMessage"] and "declined" in r["failureMessage"] for r in declined)
    assert sum(1 for r in rows if r["label"] == CREATE and r["success"] == "true") == 14


def test_slow_reports_fail_on_the_duration_assertion(rows):
    bad = failed(rows, REPORT)
    assert len(bad) == 20, "every report takes about 150 ms, so a 100 ms Duration Assertion fails all of them"
    assert all("lasted too long" in r["failureMessage"] and "100 milliseconds" in r["failureMessage"] for r in bad)


def test_assertions_are_scoped_to_their_sampler(rows):
    # The token request is answered correctly; an assertion placed too high in the tree would fail it too.
    assert all(r["success"] == "true" for r in rows if r["label"] == TOKEN)
    # Every failure explains itself.
    assert all(r["failureMessage"] for r in rows if r["success"] == "false")
