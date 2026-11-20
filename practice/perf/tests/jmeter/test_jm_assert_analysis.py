"""jm_assert_ exercise 2: exercises/jmeter/jm_assert_analysis.py explains the failures in a JTL."""

from pathlib import Path

import pytest
from jmeter.jm_assert_analysis import (
    NO_MESSAGE,
    failure_groups,
    label_summary,
    normalise_message,
    require_columns,
    unexplained_failures,
)
from jm_assert_fixture import serve
from load_tools import ROOT, read_jtl, run_jmeter

pytestmark = pytest.mark.exercise

# The reference plan of exercise 1 produces the real run, so this exercise does not depend on solving that one.
REFERENCE_PLAN = ROOT / "solutions" / "jmeter" / "jm_assert_plan.jmx"
SLOW = "The operation lasted too long: It took {} milliseconds, but should not have lasted longer than 100 milliseconds."


def row(label, success, message="", code="200"):
    return {"label": label, "success": success, "failureMessage": message, "responseCode": code}


SYNTHETIC = [
    row("GET /report", "false", SLOW.format(151)),
    row("GET /report", "false", SLOW.format(153)),
    row("GET /report", "true"),
    row("POST /pay", "false", "", "500"),
    row("POST /pay", "false", "payment not created: expected HTTP 201", "500"),
    row("POST /pay", "true", "", "201"),
    row("POST /pay", "true", "", "201"),
    row("GET /list", "true"),
]


def test_normalise_message_groups_numbers():
    assert normalise_message("  " + SLOW.format(151) + " ") == normalise_message(SLOW.format(1530))
    assert "<n>" in normalise_message(SLOW.format(151)) and "151" not in normalise_message(SLOW.format(151))
    assert normalise_message("No results for path: $['data']") == "No results for path: $['data']"


def test_failure_groups_are_counted_and_ordered():
    groups = failure_groups(SYNTHETIC)
    assert groups[0] == ("GET /report", normalise_message(SLOW.format(1)), 2)
    assert ("POST /pay", NO_MESSAGE, 1) in groups
    assert ("POST /pay", "payment not created: expected HTTP <n>", 1) in groups  # numbers normalised too
    assert len(groups) == 3
    assert [g[1] for g in groups[1:]] == sorted(g[1] for g in groups[1:])  # ties: by label, then message


def test_label_summary():
    s = label_summary(SYNTHETIC)
    assert s["GET /report"] == {"samples": 3, "failures": 2, "error_pct": 66.67}
    assert s["POST /pay"] == {"samples": 4, "failures": 2, "error_pct": 50.0}
    assert s["GET /list"] == {"samples": 1, "failures": 0, "error_pct": 0.0}


def test_unexplained_failures():
    assert unexplained_failures(SYNTHETIC) == [SYNTHETIC[3]]


def test_missing_columns_are_named():
    with pytest.raises(ValueError, match="failureMessage"):
        failure_groups([{"label": "x", "success": "false"}])
    with pytest.raises(ValueError):
        require_columns([], ["label"])
    require_columns(SYNTHETIC, ["label", "success"])  # no error


def test_on_a_real_run(tmp_path):
    with serve() as base:
        props = {"port": base.rsplit(":", 1)[1], "threads": 2, "loops": 10,
                 "jmeter.save.saveservice.timestamp_format": "HH:mm:ss.SSS"}
        rows = read_jtl(run_jmeter(REFERENCE_PLAN, props, tmp_path))
    groups = {(label, msg): n for label, msg, n in failure_groups(rows)}
    assert groups[("GET /v1/reports/settlement", normalise_message(SLOW.format(1)))] == 20
    assert groups[("GET /v1/payments", "No results for path: $['data']")] == 5
    assert groups[("POST /v1/payments", "payment not created: expected HTTP <n>")] == 4
    assert sum(n for (label, _), n in groups.items() if label == "POST /v1/payments") == 6
    assert label_summary(rows)["POST /v1/payments"]["error_pct"] == 30.0
    assert unexplained_failures(rows) == []
