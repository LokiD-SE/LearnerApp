"""jm_dash_ exercise 3: exercises/jmeter/jm_dash_gate.py, a CI gate over statistics.json.

``fixtures/jm_dash_statistics.json`` is the real statistics.json of the lesson's run (20 November 2026, default
percentiles 90/95/99): 62 samples, 11 failures (17.74 %), during which ``jmeter -n`` itself exited 0.
No JMeter run is needed here.
"""

import json
from pathlib import Path

import pytest
from jmeter.jm_dash_gate import Check, GateInputError, evaluate, main, metric_key

pytestmark = pytest.mark.exercise

REAL = Path(__file__).parent / "fixtures" / "jm_dash_statistics.json"


@pytest.fixture
def stats():
    return json.loads(REAL.read_text())


def write(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return path


def test_metric_key():
    assert metric_key("error_pct", (90, 95, 99)) == "errorPct"
    assert metric_key("mean_ms", (90, 95, 99)) == "meanResTime"
    assert metric_key("p90_ms", (90, 95, 99)) == "pct1ResTime"
    assert metric_key("p95_ms", (90, 95, 99)) == "pct2ResTime"
    assert metric_key("p95_ms", (50, 95, 99.9)) == "pct2ResTime"
    assert metric_key("p99.9_ms", (50, 95, 99.9)) == "pct3ResTime"
    for bad in ("p75_ms", "max_ms", "pxx_ms", "p95"):
        with pytest.raises(GateInputError):
            metric_key(bad, (90, 95, 99))


def test_evaluate_on_the_real_run(stats):
    checks = evaluate(stats, {"Total": {"error_pct": 1, "p95_ms": 300},
                              "POST /auth/token": {"error_pct": 0}})
    assert [(c.label, c.metric, c.ok) for c in checks] == [
        ("Total", "error_pct", False), ("Total", "p95_ms", True), ("POST /auth/token", "error_pct", True)]
    assert checks[0].actual == pytest.approx(17.741936)
    assert checks[0].limit == 1.0
    assert checks[1].actual == 152.0  # the 95th percentile (pct2ResTime) of the real run


def test_limit_is_inclusive():
    assert Check("Total", "p95_ms", 152, 152.0).ok
    assert not Check("Total", "p95_ms", 151, 152.0).ok


@pytest.mark.parametrize("slo, kwargs, match", [
    ({"GET /v1/refunds": {"error_pct": 1}}, {}, "GET /v1/refunds"),
    ({"Total": {"p75_ms": 100}}, {}, "p75_ms"),
    ({"Total": {"apdex": 0.9}}, {}, "apdex"),
    ({"POST /auth/token": {"error_pct": 1}}, {"min_samples": 10}, "POST /auth/token"),
    ({}, {}, "no checks"),
    ({"Total": {}}, {}, "no checks"),
    ({"Total": {"error_pct": 1}}, {"percentiles": (90, 95)}, "three"),
])
def test_cannot_judge(stats, slo, kwargs, match):
    with pytest.raises(GateInputError, match=match):
        evaluate(stats, slo, **kwargs)


def test_gate_input_error_is_a_value_error():
    assert issubclass(GateInputError, ValueError)


def test_main_fails_the_real_run(tmp_path, capsys):
    slo = write(tmp_path, "slo.json", {"Total": {"error_pct": 1.0, "p95_ms": 300}})
    assert main([str(REAL), "--slo", str(slo)]) == 1
    out = capsys.readouterr().out.splitlines()
    assert out == ["FAIL Total error_pct 17.74 (limit 1)", "PASS Total p95_ms 152.00 (limit 300)", "1 passed, 1 failed"]


def test_main_passes(tmp_path, capsys):
    slo = write(tmp_path, "slo.json", {"GET /v1/reports/settlement": {"error_pct": 0, "p99_ms": 500}})
    assert main([str(REAL), "--slo", str(slo), "--min-samples", "20"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "2 passed, 0 failed"


def test_main_with_other_percentiles(tmp_path, capsys):
    stats = json.loads(REAL.read_text())
    stats["Total"]["pct1ResTime"] = 2.0  # pretend the report was generated with aggregate_rpt_pct1=50
    report = write(tmp_path, "statistics.json", stats)
    slo = write(tmp_path, "slo.json", {"Total": {"p50_ms": 5}})
    assert main([str(report), "--slo", str(slo), "--percentiles", "50,95,99"]) == 0
    assert main([str(report), "--slo", str(slo)]) == 2  # 90,95,99 has no p50
    assert "p50_ms" in capsys.readouterr().err


def test_main_returns_2_when_it_cannot_judge(tmp_path, capsys):
    slo = write(tmp_path, "slo.json", {"Total": {"error_pct": 1}})
    assert main([str(tmp_path / "missing.json"), "--slo", str(slo)]) == 2
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    assert main([str(broken), "--slo", str(slo)]) == 2
    assert main([str(REAL), "--slo", str(write(tmp_path, "empty.json", {}))]) == 2
    err = capsys.readouterr().err
    assert err.count("ERROR") == 3
