"""Checks exercises/devsecops/cicd_gate.py: one gate over several scanners, with expiring baselines."""

import datetime

import pytest
from cicd_fixture import Alert, Report
from devsecops.cicd_gate import decide, normalise_severity

pytestmark = pytest.mark.exercise

TODAY = datetime.date(2026, 11, 21)
ENFORCE = {"mode": "enforce", "block_at": "high"}
TOOLS = ["zap", "sca", "sast"]


def reports(*alerts, complete=True, tools=("zap", "sca", "sast")):
    out = []
    for tool in tools:
        mine = [a for a in alerts if a.tool == tool]
        out.append(Report(tool, mine, complete))
    return out


def run(alerts=(), policy=ENFORCE, baseline=None, **kw):
    return decide(kw.pop("reports", None) or reports(*alerts), TOOLS, policy, baseline or {}, TODAY, **kw)


@pytest.mark.parametrize(
    ("tool", "raw", "expected"),
    [
        ("zap", "Informational", "info"),
        ("zap", "HIGH", "high"),
        ("zap", " medium ", "medium"),
        ("sca", "None", "info"),
        ("sca", "Critical", "critical"),
        ("sca", "low", "low"),
        ("sast", "note", "low"),
        ("sast", "Warning", "medium"),
        ("sast", "ERROR", "high"),
    ],
)
def test_every_tool_vocabulary_maps_to_the_gate_scale(tool, raw, expected):
    assert normalise_severity(tool, raw) == expected


@pytest.mark.parametrize(
    ("tool", "raw"), [("zap", "critical"), ("sast", "severe"), ("sca", ""), ("burp", "high"), ("zap", "high!")]
)
def test_an_unknown_tool_or_word_is_an_error_never_a_pass(tool, raw):
    with pytest.raises(ValueError):
        normalise_severity(tool, raw)


def test_a_clean_run_passes():
    d = run()
    assert (d.exit_code, d.blocking, d.baselined, d.expired, d.reported, d.incomplete) == (0, [], [], [], [], [])


def test_a_new_alert_at_the_threshold_blocks_and_is_named():
    high = Alert("zap", "z-1", "High")
    d = run([high, Alert("sast", "s-1", "note")])
    assert d.exit_code == 1
    assert d.blocking == [high]
    assert d.reported == [Alert("sast", "s-1", "note")]


def test_blocking_alerts_are_listed_most_severe_first_then_by_id():
    a, b, c = Alert("sca", "c-2", "Critical"), Alert("zap", "z-9", "High"), Alert("sast", "s-1", "error")
    assert run([b, a, c]).blocking == [a, c, b]


def test_the_threshold_is_configurable():
    medium = Alert("sast", "s-2", "warning")
    assert run([medium]).exit_code == 0
    assert run([medium], policy={"mode": "enforce", "block_at": "medium"}).exit_code == 1
    assert run([Alert("sca", "c-1", "critical")], policy={"mode": "enforce", "block_at": "critical"}).exit_code == 1
    assert run([Alert("sca", "c-1", "high")], policy={"mode": "enforce", "block_at": "critical"}).exit_code == 0


def test_a_baselined_alert_does_not_block():
    old = Alert("sca", "c-old", "High")
    d = run([old], baseline={"c-old": "2027-03-01"})
    assert (d.exit_code, d.blocking, d.baselined, d.expired) == (0, [], [old], [])


def test_an_acceptance_that_ran_out_blocks_again_and_is_listed_as_expired():
    old = Alert("sca", "c-old", "High")
    d = run([old], baseline={"c-old": "2026-11-20"})
    assert (d.exit_code, d.blocking, d.baselined, d.expired) == (1, [old], [], [old])


def test_the_expiry_day_itself_still_counts_and_no_expiry_never_runs_out():
    old = Alert("zap", "z-old", "High")
    assert run([old], baseline={"z-old": "2026-11-21"}).exit_code == 0
    assert run([old], baseline={"z-old": None}).exit_code == 0


def test_a_malformed_expiry_is_an_error():
    with pytest.raises(ValueError):
        run([Alert("zap", "z-1", "High")], baseline={"z-1": "next week"})


def test_a_baselined_alert_below_the_threshold_is_still_just_baselined():
    low = Alert("zap", "z-low", "Low")
    d = run([low], baseline={"z-low": None})
    assert d.baselined == [low] and d.reported == []


def test_a_scan_that_did_not_finish_fails_closed():
    d = run(reports=reports(complete=False))
    assert (d.exit_code, d.incomplete) == (2, ["sast", "sca", "zap"])


def test_a_missing_report_is_incomplete_too():
    d = run(reports=[Report("zap"), Report("sca")])
    assert (d.exit_code, d.incomplete) == (2, ["sast"])


def test_one_unfinished_tool_is_named_and_the_others_are_trusted():
    partial = [Report("zap"), Report("sca", complete=False), Report("sast")]
    d = run(reports=partial)
    assert (d.exit_code, d.incomplete) == (2, ["sca"])


def test_findings_win_over_an_unfinished_scan():
    alert = Alert("zap", "z-1", "High")
    d = run(reports=[Report("zap", [alert]), Report("sca", complete=False), Report("sast")])
    assert (d.exit_code, d.blocking, d.incomplete) == (1, [alert], ["sca"])


def test_report_mode_never_fails_but_still_lists_everything():
    alert = Alert("zap", "z-1", "High")
    d = run(reports=[Report("zap", [alert]), Report("sca", complete=False)], policy={"mode": "report", "block_at": "high"})
    assert (d.exit_code, d.blocking, d.incomplete) == (0, [alert], ["sast", "sca"])


def test_a_tool_that_was_not_expected_is_still_read():
    alert = Alert("zap", "z-1", "High")
    d = decide([Report("zap", [alert])], [], ENFORCE, {}, TODAY)
    assert (d.exit_code, d.blocking, d.incomplete) == (1, [alert], [])


@pytest.mark.parametrize(
    "policy",
    [{"mode": "enfroce", "block_at": "high"}, {"mode": "enforce", "block_at": "severe"}, {"block_at": "high"}, {"mode": "enforce"}],
)
def test_an_unknown_policy_is_an_error(policy):
    with pytest.raises(ValueError):
        run(policy=policy)


@pytest.mark.parametrize("mode", ["enforce", "report"])
def test_an_unknown_severity_is_an_error_even_when_nothing_else_would_block(mode):
    with pytest.raises(ValueError):
        run([Alert("sast", "s-1", "severe"), Alert("zap", "z-1", "Low")], policy={"mode": mode, "block_at": "high"})
