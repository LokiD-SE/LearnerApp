from pathlib import Path

import pytest
from fundamentals.slo_evaluate import Sample, achieved_rate, evaluate, from_jtl, latency_sli, overall, percentile
from fundamentals.slo_spec import Requirement
from load_tools import jmeter_home, read_jtl, run_jmeter
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

GET = "GET /v1/payments"
POST = "POST /v1/payments"


def lat(tx, p, ms, load=10.0, unit="req/s"):
    return Requirement("latency", tx, load, unit, percentile=p, threshold_ms=ms)


def err(tx, pct, load=10.0, unit="req/s"):
    return Requirement("errors", tx, load, unit, max_error_percent=pct)


def steady(label, elapsed, ok=None, every_ms=10, threads=4):
    ok = ok or [True] * len(elapsed)
    return [Sample(label, i * every_ms, e, k, threads) for i, (e, k) in enumerate(zip(elapsed, ok))]


def test_nearest_rank_percentile():
    values = [15, 20, 35, 40, 50]
    assert percentile(values, 30) == 20
    assert percentile(values, 40) == 20
    assert percentile(values, 50) == 35
    assert percentile(values, 100) == 50
    assert percentile(list(range(1, 101)), 95) == 95
    with pytest.raises(ValueError):
        percentile([], 50)


def test_latency_sli_counts_failures_as_bad():
    s = steady(GET, [10, 20, 300, 40], [True, False, True, True])
    assert latency_sli(s, 100) == 0.5


def test_achieved_rate():
    assert achieved_rate(steady(GET, [0] * 100, every_ms=10)) == pytest.approx(101.0, rel=0.02)


def test_latency_uses_successful_samples_only():
    # 100 fast successes plus 10 slow failures: the slow failures belong to the error-rate verdict.
    s = steady(GET, [50] * 100 + [5000] * 10, [True] * 100 + [False] * 10)
    v = evaluate(s, [lat(GET, 95, 100)])[0]
    assert (v.status, v.observed, v.samples) == ("pass", 50, 110)


def test_fail_and_error_rate():
    s = steady(POST, list(range(1, 201)), [i % 20 != 0 for i in range(200)])
    vs = evaluate(s, [lat(POST, 95, 150), err(POST, 1.0)])
    assert [v.status for v in vs] == ["fail", "fail"]
    assert vs[1].observed == 5.0
    assert overall(vs) == "fail"


def test_too_few_samples_is_inconclusive():
    vs = evaluate(steady(GET, [10] * 20), [lat(GET, 95, 100)])
    assert vs[0].status == "inconclusive" and vs[0].observed is None and "20 samples" in vs[0].note


def test_load_not_reached_is_inconclusive_even_if_fast():
    vs = evaluate(steady(GET, [10] * 200, every_ms=100), [lat(GET, 95, 100, load=50)])
    assert vs[0].status == "inconclusive" and "load not reached" in vs[0].note


def test_users_load_uses_thread_count():
    s = steady(GET, [10] * 200, threads=8)
    assert evaluate(s, [lat(GET, 95, 100, load=8, unit="users")])[0].status == "pass"
    assert evaluate(s, [lat(GET, 95, 100, load=50, unit="users")])[0].status == "inconclusive"


def test_overall():
    def v(status):
        return type("V", (), {"status": status})()

    assert overall([v("pass"), v("pass")]) == "pass"
    assert overall([v("pass"), v("inconclusive")]) == "inconclusive"
    assert overall([v("inconclusive"), v("fail")]) == "fail"


@pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")
def test_real_jmeter_run(tmp_path):
    # 30% of payment creations fail on purpose; listing stays healthy.
    with serve(TargetConfig(latency_ms=5, error_rate=0.3)) as base:
        jtl = run_jmeter(Path(__file__).parent / "slo_payments.jmx", {"port": base.rsplit(":", 1)[1]}, tmp_path)
    samples = from_jtl(read_jtl(jtl))
    assert {s.label for s in samples} == {"POST /auth/token", GET, POST}
    vs = evaluate(samples, [lat(GET, 95, 2000, load=5), err(POST, 1.0, load=5), lat(GET, 95, 2000, load=10**6)])
    assert [v.status for v in vs] == ["pass", "fail", "inconclusive"]
    assert vs[1].observed > 1.0
    assert overall(vs) == "fail"
