"""jm_dash_ exercise 1: exercises/jmeter/jm_dash_report.py builds the properties and the ``jmeter -g`` command.

The last test runs your command with real JMeter on a JTL from the reference assertion plan (62 samples, 11
failures, counts fixed by the practice API) and checks the dashboard it generates.
"""

import json
import re

import pytest
from jm_dash_fixture import jmeter_binary, make_jtl, run_jmeter_args
from jmeter.jm_dash_report import report_command, report_properties

pytestmark = pytest.mark.exercise

P = "jmeter.reportgenerator."


def test_defaults():
    assert report_properties() == {
        P + "apdex_satisfied_threshold": "500",
        P + "apdex_tolerated_threshold": "1500",
        "aggregate_rpt_pct1": "90",
        "aggregate_rpt_pct2": "95",
        "aggregate_rpt_pct3": "99",
    }


def test_percentile_properties_have_no_reportgenerator_prefix():
    props = report_properties(percentiles=(50, 95, 99.9))
    assert props["aggregate_rpt_pct1"] == "50" and props["aggregate_rpt_pct3"] == "99.9"
    assert not any(k.startswith(P + "aggregate") for k in props)


def test_optional_settings():
    props = report_properties(100, 400, title="SandPay checkout", sample_filter="GET .*",
                              per_transaction={"GET /v1/reports/settlement": (200, 800), "POST .*": (50, 200)})
    assert props[P + "report_title"] == "SandPay checkout"
    assert props[P + "sample_filter"] == "GET .*"
    assert props[P + "apdex_per_transaction"] == "GET /v1/reports/settlement:200|800;POST .*:50|200;"
    assert props[P + "apdex_satisfied_threshold"] == "100"
    assert all(isinstance(v, str) for v in props.values())


@pytest.mark.parametrize("kwargs", [
    {"satisfied_ms": 0},
    {"satisfied_ms": 1500, "tolerated_ms": 1500},
    {"satisfied_ms": 2000},
    {"percentiles": (90, 95)},
    {"percentiles": (95, 90, 99)},
    {"percentiles": (90, 90, 99)},
    {"percentiles": (90, 95, 100)},
    {"sample_filter": "GET (unclosed"},
    {"per_transaction": {"GET /a": (300, 100)}},
    {"per_transaction": {"a;b": (100, 300)}},
    {"per_transaction": {"": (100, 300)}},
])
def test_rejects_bad_settings(kwargs):
    with pytest.raises(ValueError):
        report_properties(**kwargs)


def test_command_line(tmp_path):
    jtl = tmp_path / "run.jtl"
    jtl.write_text("timeStamp,elapsed,label\n")
    cmd = report_command("jmeter", jtl, tmp_path / "report", {"b": "2", "a": "x y"})
    assert cmd == ["jmeter", "-g", str(jtl), "-o", str(tmp_path / "report"), "-Ja=x y", "-Jb=2"]
    (tmp_path / "empty").mkdir()
    assert report_command("jmeter", jtl, tmp_path / "empty", {})[4] == str(tmp_path / "empty")


def test_command_refuses_what_jmeter_would_refuse(tmp_path):
    with pytest.raises(FileNotFoundError):
        report_command("jmeter", tmp_path / "missing.jtl", tmp_path / "report", {})
    jtl = tmp_path / "run.jtl"
    jtl.write_text("timeStamp,elapsed,label\n")
    (tmp_path / "report").mkdir()
    (tmp_path / "report" / "index.html").write_text("old run")
    with pytest.raises(FileExistsError):
        report_command("jmeter", jtl, tmp_path / "report", {})


def _table(js, table_id):
    marker = f'createTable($("#{table_id}"), '
    return json.JSONDecoder().raw_decode(js, js.index(marker) + len(marker))[0]


def test_real_dashboard(tmp_path):
    jtl = make_jtl(tmp_path / "run")
    props = report_properties(100, 1000, percentiles=(50, 95, 99), title="SandPay checkout",
                              sample_filter="(GET|POST) /v1/.*",  # matched against the WHOLE name
                              per_transaction={"GET /v1/reports/settlement": (400, 1600)})
    out = tmp_path / "report"
    proc = run_jmeter_args(report_command(jmeter_binary(), jtl, out, props), cwd=tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    stats = json.loads((out / "statistics.json").read_text())
    # sample_filter drops the token samples BEFORE the statistics are calculated, so Total changes too.
    assert set(stats) == {"Total", "GET /v1/payments", "POST /v1/payments", "GET /v1/reports/settlement"}
    assert (stats["Total"]["sampleCount"], stats["Total"]["errorCount"]) == (60, 11)
    js = (out / "content" / "js" / "dashboard.js").read_text()
    assert _table(js, "statisticsTable")["titles"][8:11] == ["50th pct", "95th pct", "99th pct"]
    apdex = {row["data"][3]: row["data"][:3] for row in _table(js, "apdexTable")["items"]}
    assert apdex["GET /v1/reports/settlement"][1:] == [400, 1600]
    assert apdex["GET /v1/payments"][1:] == [100, 1000]
    assert apdex["GET /v1/reports/settlement"][0] == 1.0  # ~150 ms is satisfied when T = 400
    assert re.search(r"<title>\s*SandPay checkout", (out / "index.html").read_text())
