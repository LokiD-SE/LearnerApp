"""jm_logic_ exercise 3: predict a plan's sample counts and read transaction samples (jmeter/jm_logic_counts.py).

The last test runs a reference copy of the solved journey plan (fixtures/jm_logic_journey_ref.jmx) with real
JMeter and checks your prediction against what JMeter recorded.
"""

from collections import Counter
from pathlib import Path

import pytest
from jm_logic_fixture import serve
from jmeter.jm_logic_counts import predict_journey, throughput_passes, transaction_report
from load_tools import jmeter_home, read_jtl, run_jmeter

pytestmark = pytest.mark.exercise

REF = Path(__file__).parent / "fixtures" / "jm_logic_journey_ref.jmx"


def tx(label, inside, failing, success=None):
    ok = success if success is not None else ("false" if failing else "true")
    return {"label": label, "success": ok,
            "responseMessage": f"Number of samples in transaction : {inside}, number of failing samples : {failing}"}


def test_throughput_passes_follows_jmeters_rule():
    assert throughput_passes(25, 8) == [False, False, True, False, False, False, True, False]
    assert throughput_passes(50, 6) == [False, True, False, True, False, True]
    assert sum(throughput_passes(30, 100)) == 30
    assert throughput_passes(100, 3) == [True, True, True]
    assert throughput_passes(0, 3) == [False, False, False]
    assert throughput_passes(40, 0) == []


@pytest.mark.parametrize("percent,iterations", [(-1, 5), (101, 5), (50, -1)])
def test_throughput_passes_rejects_impossible_input(percent, iterations):
    with pytest.raises(ValueError):
        throughput_passes(percent, iterations)


def test_predict_journey_counts_every_label():
    assert predict_journey(3, 8, 25) == Counter({"POST /auth/token": 3, "POST /v1/payments": 24,
                                                 "GET /v1/payments/{id}": 24, "Checkout": 24,
                                                 "GET /v1/reports/settlement": 6})
    assert predict_journey(2, 1, 50)["GET /v1/reports/settlement"] == 0


def test_transaction_report_adds_up_transaction_rows_only():
    rows = [tx("Checkout", 2, 0), tx("Checkout", 2, 1), tx("Checkout", 1, 1),
            {"label": "POST /v1/payments", "success": "false", "responseMessage": "Internal Server Error"},
            tx("Refund", 3, 0)]
    assert transaction_report(rows) == {
        "Checkout": {"count": 3, "failed": 2, "samples": 5, "failing_samples": 2},
        "Refund": {"count": 1, "failed": 0, "samples": 3, "failing_samples": 0},
    }
    assert transaction_report([]) == {}


@pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")
def test_prediction_matches_a_real_run(tmp_path):
    with serve() as base:
        props = {"port": base.rsplit(":", 1)[1], "threads": 2, "loops": 10, "report_percent": 30}
        rows = read_jtl(run_jmeter(REF, props, tmp_path))
    assert Counter(r["label"] for r in rows) == predict_journey(2, 10, 30)
    # 20 payments, every 4th a 500 whose look-up is then a 404: 5 checkouts with 2 failing samples each
    assert transaction_report(rows) == {"Checkout": {"count": 20, "failed": 5, "samples": 40, "failing_samples": 10}}
