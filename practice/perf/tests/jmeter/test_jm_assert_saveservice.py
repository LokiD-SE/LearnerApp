"""jm_assert_ exercise 3: exercises/jmeter/jm_assert_saveservice.py chooses exactly the JTL columns a run needs."""

from pathlib import Path

import pytest
from jmeter.jm_assert_saveservice import PREFIX, csv_save_properties, expected_header, missing_columns
from load_tools import ROOT, run_jmeter
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

LEAN = {"timeStamp", "elapsed", "label", "responseCode", "success", "failureMessage", "Latency", "Connect"}
SMOKE = ROOT / "tests" / "support" / "fixtures" / "smoke.jmx"


def test_expected_header_uses_jmeters_order():
    assert expected_header(LEAN) == [
        "timeStamp", "elapsed", "label", "responseCode", "success", "failureMessage", "Latency", "Connect"]
    assert expected_header({"Connect", "URL", "IdleTime", "Latency"}) == ["URL", "Latency", "IdleTime", "Connect"]


def test_paired_columns_come_together():
    assert expected_header({"grpThreads"}) == ["grpThreads", "allThreads"]
    assert expected_header({"ErrorCount", "label"}) == ["label", "SampleCount", "ErrorCount"]


def test_properties_switch_every_column():
    props = csv_save_properties(LEAN)
    assert props[PREFIX + "output_format"] == "csv" and props[PREFIX + "print_field_names"] == "true"
    assert props[PREFIX + "assertion_results_failure_message"] == "true"
    assert props[PREFIX + "latency"] == "true" and props[PREFIX + "connect_time"] == "true"
    for off in ("response_message", "thread_name", "data_type", "bytes", "sent_bytes", "thread_counts", "url",
                "idle_time", "hostname", "filename", "encoding", "sample_count"):
        assert props[PREFIX + off] == "false", off
    assert props[PREFIX + "timestamp_format"] == "yyyy/MM/dd HH:mm:ss.SSS"
    assert csv_save_properties(LEAN - {"timeStamp"})[PREFIX + "timestamp_format"] == "none"
    assert csv_save_properties(LEAN, "HH:mm:ss")[PREFIX + "timestamp_format"] == "HH:mm:ss"


def test_unknown_columns_are_rejected():
    with pytest.raises(ValueError, match="latency"):
        csv_save_properties({"label", "latency"})  # the column is "Latency"
    with pytest.raises(ValueError):
        expected_header({"responseTime"})


def test_missing_columns():
    assert missing_columns(["label", "success"], ["label", "failureMessage", "Connect"]) == ["failureMessage", "Connect"]
    assert missing_columns(["label"], []) == []


def test_jmeter_writes_exactly_that_header(tmp_path):
    with serve(TargetConfig(latency_ms=1)) as base:
        props = {"port": base.rsplit(":", 1)[1], "threads": 1, "loops": 2, **csv_save_properties(LEAN, "HH:mm:ss.SSS")}
        jtl = run_jmeter(SMOKE, props, tmp_path)
    lines = Path(jtl).read_text().splitlines()
    assert lines[0].split(",") == expected_header(LEAN)
    assert len(lines) == 3
