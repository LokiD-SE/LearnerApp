"""jm_dash_ exercise 2: exercises/jmeter/jm_dash_stats.py reads statistics.json and the dashboard.js tables.

The module fixture generates one real dashboard (JMeter run + ``jmeter -g``) with percentiles 50/95/99 and Apdex
T = 100 ms, F = 1000 ms. The practice API's failures come from a request counter, so the counts and the
error-based Apdex values are exact; the settlement report takes about 150 ms, so it is "tolerating".
"""

import json

import pytest
from jm_dash_fixture import LABELS, jmeter_binary, make_jtl, run_jmeter_args
from jmeter.jm_dash_stats import (
    apdex_by_label,
    error_types,
    load_statistics,
    percentile_name,
    read_dashboard_table,
)

pytestmark = pytest.mark.exercise

SYNTHETIC_JS = """$(document).ready(function() {
    createTable($("#apdexTable"), {"supportsControllersDiscrimination": true, "overall": {"data": [0.5, 100, 400, "Total"], "isController": false}, "titles": ["Apdex", "T (Toleration threshold)", "F (Frustration threshold)", "Label"], "items": [{"data": [0.25, 100, 400, "GET /a"], "isController": false}, {"data": [1.0, 200, 800, "GET /b"], "isController": false}]}, function(index, item){
        return item;
    }, [[0, 0]], 3);
    createTable($("#errorsTable"), {"supportsControllersDiscrimination": false, "titles": ["Type of error", "Number of errors", "% in errors", "% in all samples"], "items": [{"data": ["500/Internal Server Error", 2, 40.0, 2.0], "isController": false}, {"data": ["No results for path: $['data']", 3, 60.0, 3.0], "isController": false}, {"data": ["404/Not Found", 2, 40.0, 2.0], "isController": false}]}, function(index, item){
        return item;
    }, [[1, 1]]);
});
"""


@pytest.fixture(scope="module")
def dashboard(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("jm_dash_stats")
    jtl = make_jtl(tmp / "run")
    out = tmp / "report"
    cmd = [jmeter_binary(), "-g", jtl, "-o", out, "-Jaggregate_rpt_pct1=50",
           "-Jjmeter.reportgenerator.apdex_satisfied_threshold=100",
           "-Jjmeter.reportgenerator.apdex_tolerated_threshold=1000"]
    proc = run_jmeter_args(cmd, cwd=tmp)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return out


def test_percentile_name():
    assert percentile_name(95) == "p95_ms"
    assert percentile_name(99.9) == "p99.9_ms"


def test_load_statistics_renames_and_maps_percentiles(tmp_path):
    raw = {"Total": {"transaction": "Total", "sampleCount": 4, "errorCount": 1, "errorPct": 25.0, "meanResTime": 10.5,
                     "medianResTime": 9.0, "minResTime": 2.0, "maxResTime": 30.0, "pct1ResTime": 9.0,
                     "pct2ResTime": 28.0, "pct3ResTime": 30.0, "throughput": 2.0, "receivedKBytesPerSec": 1.0,
                     "sentKBytesPerSec": 1.0}}
    path = tmp_path / "statistics.json"
    path.write_text(json.dumps(raw))
    stats = load_statistics(path, (50, 95, 99.9))
    assert stats["Total"] == {"samples": 4, "errors": 1, "error_pct": 25.0, "mean_ms": 10.5, "median_ms": 9.0,
                              "min_ms": 2.0, "max_ms": 30.0, "throughput_per_s": 2.0, "p50_ms": 9.0,
                              "p95_ms": 28.0, "p99.9_ms": 30.0}
    assert "p90_ms" not in load_statistics(path, (50, 95, 99.9))["Total"]
    assert load_statistics(path)["Total"]["p90_ms"] == 9.0  # default 90/95/99: pct1 is the 90th


def test_load_statistics_rejects(tmp_path):
    path = tmp_path / "statistics.json"
    path.write_text(json.dumps({"GET /a": {}}))
    with pytest.raises(ValueError, match="Total"):
        load_statistics(path)
    with pytest.raises(ValueError):
        load_statistics(path, (90, 95))


def test_tables_from_synthetic_js():
    assert read_dashboard_table(SYNTHETIC_JS, "apdexTable")["overall"]["data"][0] == 0.5
    with pytest.raises(ValueError, match="statisticsTable"):
        read_dashboard_table(SYNTHETIC_JS, "statisticsTable")
    assert apdex_by_label(SYNTHETIC_JS) == {
        "Total": {"apdex": 0.5, "t_ms": 100, "f_ms": 400},
        "GET /a": {"apdex": 0.25, "t_ms": 100, "f_ms": 400},
        "GET /b": {"apdex": 1.0, "t_ms": 200, "f_ms": 800},
    }
    assert error_types(SYNTHETIC_JS) == [
        ("No results for path: $['data']", 3),
        ("404/Not Found", 2),
        ("500/Internal Server Error", 2),
    ]


def test_real_statistics(dashboard):
    stats = load_statistics(dashboard / "statistics.json", (50, 95, 99))
    assert set(stats) == {"Total", *LABELS}
    assert {k: (v["samples"], v["errors"]) for k, v in stats.items()} == {
        "Total": (62, 11), "POST /auth/token": (2, 0), "GET /v1/payments": (20, 5),
        "POST /v1/payments": (20, 6), "GET /v1/reports/settlement": (20, 0)}
    assert stats["POST /v1/payments"]["error_pct"] == 30.0
    report = stats["GET /v1/reports/settlement"]
    assert 140 <= report["min_ms"] <= report["p50_ms"] <= report["p95_ms"] <= report["max_ms"]


def test_real_apdex_and_errors(dashboard):
    js = (dashboard / "content" / "js" / "dashboard.js").read_text()
    apdex = apdex_by_label(js)
    assert {v["t_ms"] for v in apdex.values()} == {100} and {v["f_ms"] for v in apdex.values()} == {1000}
    # Failed samples are never satisfied or tolerating, whatever their time.
    assert apdex["GET /v1/payments"]["apdex"] <= 0.75
    assert apdex["POST /v1/payments"]["apdex"] <= 0.7
    # ~150 ms is between T and F: every report sample is tolerating.
    assert apdex["GET /v1/reports/settlement"]["apdex"] == 0.5
    assert error_types(js) == [
        ("No results for path: $['data']", 5),
        ("500/Internal Server Error", 4),  # a non-2xx code wins over the assertion's custom message
        ("Value in json path '$.status' expected to be 'captured', but found 'declined'", 2),
    ]
