"""Checks exercises/capstone/pcap_report.py on the engagement's real captured runs (support/pcap_data, captured
21 November 2026) and on small synthetic cases for the edge rules."""

import pytest
from capstone.pcap_report import (compare_tools, final_call, locust_percentile, locust_verdicts, render_report,
                                  steady_samples)
from pcap_fixture import read_rows, read_stats, ref

pytestmark = pytest.mark.exercise

REQUIREMENTS = [ref.parse_requirement(t) for t in [
    "p95 of POST /v1/payments < 120 ms at 24 req/s",
    "p95 of GET /v1/payments < 80 ms at 18 req/s",
    "p95 of GET /v1/payments/{id} < 80 ms at 15 req/s",
    "p95 of GET /v1/reports/settlement < 400 ms at 3 req/s",
    "error rate of POST /v1/payments below 1% at 24 req/s",
]]
PLAN = {"rates": {"POST /v1/payments": 24, "GET /v1/payments": 18, "GET /v1/payments/{id}": 15,
                  "GET /v1/reports/settlement": 3},
        "users": 21, "ceiling_rps": 216.2, "utilisation": 0.28, "run_seconds": 39}
CAVEATS = ["One machine runs the API, the load generator and the analysis.", "Timings are from 21 November 2026."]


def V(tx, status, observed=20.0, kind="latency", note=""):
    return ref.Verdict(tx, kind, 100.0, observed, status, 500, note)


def jmeter_verdicts():
    samples = steady_samples(ref.from_jtl(read_rows("jmeter_target")), 5)
    return ref.evaluate(samples, REQUIREMENTS)


# ---- steady_samples --------------------------------------------------------------------------------------------

def test_steady_samples_drop_the_warm_up():
    samples = ref.from_jtl(read_rows("jmeter_target"))
    steady = steady_samples(samples, 5)
    first = min(s.timestamp_ms for s in samples)
    assert 0 < len(steady) < len(samples)
    assert all(s.timestamp_ms - first >= 5000 for s in steady)
    assert len(steady) == sum(1 for s in samples if s.timestamp_ms - first >= 5000)


def test_steady_samples_work_with_epoch_timestamps_and_empty_input():
    samples = ref.from_jtl(read_rows("jmeter_target"))
    shifted = [ref.Sample(s.label, s.timestamp_ms + 10**12, s.elapsed_ms, s.success, s.threads) for s in samples]
    assert len(steady_samples(shifted, 5)) == len(steady_samples(samples, 5))
    assert steady_samples([], 5) == []


# ---- locust_percentile -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("pct, expected", [(50, 10), (90, 10), (91, 100), (100, 100), (1, 10)])
def test_locust_percentile_is_nearest_rank_over_the_histogram(pct, expected):
    assert locust_percentile({"10": 90, "100": 10}, pct) == expected


def test_locust_percentile_sorts_numerically_not_as_text():
    assert locust_percentile({"1000": 1, "90": 1, "250": 1}, 100) == 1000
    assert locust_percentile({"1000": 1, "90": 1, "250": 1}, 34) == 250


@pytest.mark.parametrize("hist, pct", [({}, 95), ({"10": 1}, 0), ({"10": 1}, 101)])
def test_locust_percentile_rejects_bad_input(hist, pct):
    with pytest.raises(ValueError):
        locust_percentile(hist, pct)


# ---- locust_verdicts ---------------------------------------------------------------------------------------------

def test_the_target_run_meets_every_requirement_in_locust_too():
    verdicts = locust_verdicts(read_stats("locust_target"), REQUIREMENTS)
    assert [v.status for v in verdicts] == ["pass"] * 5
    by = {(v.transaction, v.kind): v for v in verdicts}
    assert by[("POST /v1/payments", "latency")].observed <= 120
    assert by[("GET /v1/reports/settlement", "latency")].observed <= 400
    assert by[("POST /v1/payments", "errors")].observed == 0
    assert all(v.note.startswith("achieved ") for v in verdicts)
    assert by[("POST /v1/payments", "latency")].samples == 1199


def test_the_stress_run_fails_every_latency_requirement_but_not_the_error_one():
    verdicts = locust_verdicts(read_stats("locust_stress"), REQUIREMENTS)
    status = {(v.transaction, v.kind): v.status for v in verdicts}
    assert [s for (tx, kind), s in status.items() if kind == "latency"] == ["fail"] * 4
    assert status[("POST /v1/payments", "errors")] == "pass"


def test_too_few_samples_is_inconclusive_not_pass():
    verdicts = locust_verdicts(read_stats("locust_target"), REQUIREMENTS, min_samples=5000)
    assert {v.status for v in verdicts} == {"inconclusive"}
    assert verdicts[0].observed is None and verdicts[0].note == "only 1199 samples (need 5000)"


def test_a_transaction_that_never_ran_is_inconclusive_with_zero_samples():
    req = ref.Requirement("latency", "GET /v1/nothing", 5.0, "req/s", percentile=95.0, threshold_ms=100.0)
    [verdict] = locust_verdicts(read_stats("locust_target"), [req])
    assert (verdict.status, verdict.samples, verdict.observed) == ("inconclusive", 0, None)


def test_a_load_that_was_not_reached_is_inconclusive_but_keeps_the_observed_value():
    req = ref.Requirement("latency", "GET /v1/reports/settlement", 100.0, "req/s", percentile=95.0, threshold_ms=400.0)
    [verdict] = locust_verdicts(read_stats("locust_target"), [req])
    assert verdict.status == "inconclusive" and verdict.note.startswith("load not reached")
    assert verdict.observed is not None and verdict.observed <= 400


def test_a_load_stated_in_users_cannot_be_checked_from_locust_totals():
    req = ref.Requirement("latency", "POST /v1/payments", 20.0, "users", percentile=95.0, threshold_ms=120.0)
    [verdict] = locust_verdicts(read_stats("locust_target"), [req])
    assert verdict.status == "inconclusive" and "users" in verdict.note


def test_an_error_rate_above_the_limit_fails():
    entry = {"name": "POST /v1/payments", "num_requests": 1000, "num_failures": 25, "response_times": {"40": 1000},
             "start_time": 0.0, "last_request_timestamp": 20.0}
    req = ref.parse_requirement("error rate of POST /v1/payments below 1% at 40 req/s")
    [verdict] = locust_verdicts([entry], [req])
    assert (verdict.observed, verdict.status) == (2.5, "fail")


# ---- compare_tools -----------------------------------------------------------------------------------------------

def test_jmeter_and_locust_agree_on_the_target_run():
    agreement = compare_tools(jmeter_verdicts(), locust_verdicts(read_stats("locust_target"), REQUIREMENTS))
    assert set(agreement.values()) == {"agree"} and len(agreement) == 5
    assert ("GET /v1/reports/settlement", "latency") in agreement


def test_jmeter_at_target_load_and_locust_at_stress_do_not_agree():
    agreement = compare_tools(jmeter_verdicts(), locust_verdicts(read_stats("locust_stress"), REQUIREMENTS))
    assert agreement[("POST /v1/payments", "latency")] == "differ"
    assert agreement[("POST /v1/payments", "errors")] == "agree"


@pytest.mark.parametrize("x, y, expected", [
    (V("T", "pass", 247), V("T", "pass", 240), "agree"),          # Locust rounds to two significant digits
    (V("T", "pass", 20), V("T", "pass", 29), "agree"),            # 9 ms apart, inside the 10 ms slack
    (V("T", "pass", 20), V("T", "pass", 31), "differ"),           # 11 ms apart
    (V("T", "pass", 500), V("T", "pass", 640), "agree"),          # 28 %: inside 30 % of the smaller
    (V("T", "pass", 500), V("T", "pass", 660), "differ"),         # 32 %
    (V("T", "pass", 90), V("T", "fail", 91), "differ"),           # close numbers, different verdicts
    (V("T", "pass", None), V("T", "pass", 91), "not-comparable"),
])
def test_agreement_rules(x, y, expected):
    assert compare_tools([x], [y]) == {("T", "latency"): expected}


def test_a_requirement_missing_from_one_tool_is_not_comparable():
    out = compare_tools([V("A", "pass"), V("B", "pass")], [V("A", "pass")])
    assert out == {("A", "latency"): "agree", ("B", "latency"): "not-comparable"}


# ---- final_call --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("by_tool, agreement, expected", [
    ({"JMeter": [V("A", "pass")], "Locust": [V("A", "pass")]}, None, "pass"),
    ({"JMeter": [V("A", "pass")], "Locust": [V("A", "pass")]}, {("A", "latency"): "agree"}, "pass"),
    ({"JMeter": [V("A", "pass"), V("B", "fail")], "Locust": [V("A", "pass")]}, None, "fail"),
    ({"JMeter": [V("A", "inconclusive")], "Locust": [V("A", "fail")]}, None, "fail"),
    ({"JMeter": [V("A", "pass"), V("B", "inconclusive")], "Locust": [V("A", "pass")]}, None, "inconclusive"),
    ({"JMeter": [V("A", "pass")], "Locust": [V("A", "pass")]}, {("A", "latency"): "differ"}, "inconclusive"),
    ({"JMeter": [V("A", "pass")], "Locust": [V("A", "pass")]}, {("A", "latency"): "not-comparable"}, "pass"),
    ({"JMeter": [V("A", "pass")], "Locust": []}, None, "inconclusive"),
])
def test_final_call(by_tool, agreement, expected):
    assert final_call(by_tool, agreement) == expected


def test_final_call_needs_at_least_one_tool():
    with pytest.raises(ValueError):
        final_call({})


# ---- render_report -----------------------------------------------------------------------------------------------

def report(by_tool, agreement=None):
    return render_report("SandPay API - settlement day", PLAN, by_tool, agreement, CAVEATS)


def test_the_target_run_report_passes_with_evidence_and_caveats():
    jm, lc = jmeter_verdicts(), locust_verdicts(read_stats("locust_target"), REQUIREMENTS)
    text = report({"JMeter": jm, "Locust": lc}, compare_tools(jm, lc))
    headings = [line for line in text.splitlines() if line.startswith("#")]
    assert headings == ["# SandPay API - settlement day", "## Verdict", "## Plan", "## Evidence", "## Tool agreement",
                        "## Caveats"]
    verdict_line = text.split("## Verdict")[1].split("## Plan")[0].strip()
    assert verdict_line.startswith("**PASS** - ")
    assert "21 users" in text and "216" in text and "28%" in text and "39 s" in text
    rows = [line for line in text.splitlines() if line.startswith("| JMeter") or line.startswith("| Locust")]
    assert len(rows) == 10
    assert any("| Locust | POST /v1/payments | latency | 120 |" in r for r in rows)
    assert "- One machine runs the API, the load generator and the analysis." in text
    assert "- POST /v1/payments [latency]: agree" in text


def test_a_failing_run_never_says_pass_and_names_what_failed():
    text = report({"Locust stress": locust_verdicts(read_stats("locust_stress"), REQUIREMENTS)})
    verdict_line = text.split("## Verdict")[1].split("## Plan")[0].strip()
    assert verdict_line.startswith("**FAIL** - failed: ")
    assert "POST /v1/payments (Locust stress)" in verdict_line and "**PASS**" not in text
    assert "only one tool ran" in text


def test_an_inconclusive_run_says_why():
    by_tool = {"JMeter": [V("A", "pass"), V("B", "inconclusive", None, note="only 40 samples (need 100)")],
               "Locust": [V("A", "pass"), V("B", "pass")]}
    verdict_line = report(by_tool).split("## Verdict")[1].split("## Plan")[0].strip()
    assert verdict_line.startswith("**INCONCLUSIVE** - cannot support a verdict: ")
    assert "B (JMeter): only 40 samples (need 100)" in verdict_line


def test_tools_that_differ_make_the_call_inconclusive_and_the_report_says_so():
    by_tool = {"JMeter": [V("A", "pass", 50)], "Locust": [V("A", "pass", 90)]}
    text = report(by_tool, compare_tools(by_tool["JMeter"], by_tool["Locust"]))
    assert "**INCONCLUSIVE**" in text and "A [latency]: the tools differ" in text


def test_a_report_without_caveats_is_refused():
    with pytest.raises(ValueError):
        render_report("t", PLAN, {"JMeter": [V("A", "pass")]}, None, [])

