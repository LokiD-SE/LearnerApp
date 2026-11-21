"""Checks exercises/analysis/pci_gate.py: a regression gate with three exit codes (it uses pci_baseline).

The runs come from support/pci_data/history.json (real Locust runs, captured on 21 November 2026); one test makes a
fresh real run against a target that fails most payment creations."""

import json

import pytest
from analysis.pci_baseline import load_history
from analysis.pci_gate import EXIT_INVALID, EXIT_PASS, EXIT_REGRESSION, evaluate, main, validity_problems
from pci_fixture import history, run_summary

pytestmark = pytest.mark.exercise

RUNS = history()
BASE = RUNS["main"][-10:]  # the ten runs the baseline window sees


def test_the_exit_codes_are_zero_one_and_two():
    assert (EXIT_PASS, EXIT_REGRESSION, EXIT_INVALID) == (0, 1, 2)


def test_validity_problems_come_in_a_fixed_order():
    run = {"samples": 50, "generator_cpu_max": 95}
    assert validity_problems(run) == ["only 50 samples (need 80)", "generator CPU reached 95% (limit 80%)",
                                      "p95_ms is missing"]
    assert validity_problems({"samples": 120, "generator_cpu_max": 80, "p95_ms": 60}) == []  # 80 is not above 80
    assert validity_problems({"p95_ms": 60}) == ["only 0 samples (need 80)"]
    assert validity_problems({"samples": 79, "p95_ms": 60}, min_samples=79) == []


def test_a_run_of_the_same_build_passes():
    result = evaluate(RUNS["same"][0], BASE)
    assert result == {"code": 0, "status": "pass", "reasons": []}


def test_a_slower_build_fails_with_the_numbers_in_the_reason():
    result = evaluate(RUNS["small"][1], BASE)  # p95 69 against a baseline median of 64
    assert result["code"] == 1 and result["status"] == "fail"
    assert result["reasons"] == ["p95 69 ms is 7.8% above the baseline median 64 ms (tolerance 7.0%)"]
    assert evaluate(RUNS["slower"][1], BASE)["code"] == 1


def test_a_failing_build_with_a_fine_p95_fails_on_its_error_rate():
    run = RUNS["failing"][0]  # 25 errors in 127 samples, p95 61 ms
    result = evaluate(run, BASE)
    assert result["code"] == 1
    assert result["reasons"] == ["error rate 19.7% is above 1.0%"]
    assert evaluate({**run, "errors": 1}, BASE)["code"] == 0  # 1 in 127 is 0.8 %, inside the 1 % allowance


def test_an_invalid_run_is_exit_two_and_is_not_compared():
    good = RUNS["same"][0]
    busy = evaluate({**good, "generator_cpu_max": 95}, BASE)
    assert busy == {"code": 2, "status": "invalid", "reasons": ["generator CPU reached 95% (limit 80%)"]}
    short = evaluate({**good, "samples": 50}, BASE)
    assert short["code"] == 2 and short["reasons"] == ["only 50 samples (need 80)"]
    # even a hopeless p95 is not judged when the measurement cannot be trusted
    assert evaluate({**RUNS["slower"][1], "generator_cpu_max": 99}, BASE)["code"] == 2


def test_two_captured_runs_are_invalid_because_the_measurement_was_poor():
    first, busy = RUNS["main"][0], RUNS["slower"][0]  # a slow start with 64 samples; a run with machine CPU at 90 %
    assert evaluate(first, BASE) == {"code": 2, "status": "invalid", "reasons": ["only 64 samples (need 80)"]}
    assert evaluate(busy, BASE) == {"code": 2, "status": "invalid",
                                    "reasons": ["generator CPU reached 90% (limit 80%)"]}


def test_the_budget_is_enforced_even_without_a_baseline():
    run = RUNS["same"][0]  # p95 62
    assert evaluate(run, [], budget_p95=200)["code"] == 0
    result = evaluate(run, [], budget_p95=50)
    assert result["code"] == 1 and result["reasons"] == ["p95 62 ms is above the budget 50 ms"]


def test_with_too_few_runs_the_gate_passes_and_says_the_baseline_is_being_built():
    assert evaluate(RUNS["slower"][1], BASE[:3])["reasons"] == ["building baseline (3 of 5 runs)"]
    assert evaluate(RUNS["slower"][1], BASE[:3])["code"] == 0  # nothing to compare with yet
    assert evaluate(RUNS["same"][0], [])["reasons"] == ["building baseline (0 of 5 runs)"]
    assert evaluate(RUNS["same"][0], BASE[:4], min_runs=4)["reasons"] == []


def test_reasons_come_in_the_order_error_budget_regression():
    run = {**RUNS["slower"][1], "errors": 30}
    result = evaluate(run, BASE, budget_p95=70)
    assert result["code"] == 1 and len(result["reasons"]) == 3
    assert [r.split()[0] for r in result["reasons"]] == ["error", "p95", "p95"]
    assert "budget" in result["reasons"][1] and "baseline" in result["reasons"][2]


def write(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return str(path)


def test_main_prints_the_verdict_and_returns_the_exit_code(tmp_path):
    hist = write(tmp_path, "history.json", BASE)
    lines = []
    assert main(["--run", write(tmp_path, "run.json", RUNS["same"][0]), "--history", hist], out=lines.append) == 0
    assert lines == ["gate: PASS"]
    lines.clear()
    code = main(["--run", write(tmp_path, "run.json", RUNS["small"][1]), "--history", hist], out=lines.append)
    assert code == 1 and lines[0] == "gate: FAIL" and lines[1].startswith("- p95 69 ms is 7.8% above")
    lines.clear()
    busy = {**RUNS["same"][0], "generator_cpu_max": 99}
    assert main(["--run", write(tmp_path, "run.json", busy), "--history", hist], out=lines.append) == 2
    assert lines[0] == "gate: INVALID"


def test_main_takes_a_budget_and_a_minimum_number_of_runs(tmp_path):
    hist = write(tmp_path, "history.json", BASE[:4])
    run = write(tmp_path, "run.json", RUNS["same"][0])
    assert main(["--run", run, "--history", hist, "--budget-p95", "50"], out=lambda s: None) == 1
    lines = []
    assert main(["--run", run, "--history", hist, "--min-runs", "4"], out=lines.append) == 0
    assert lines == ["gate: PASS"]


def test_an_unreadable_run_file_fails_closed(tmp_path):
    hist = write(tmp_path, "history.json", BASE)
    lines = []
    assert main(["--run", str(tmp_path / "missing.json"), "--history", hist], out=lines.append) == 2
    assert lines[0] == "gate: INVALID" and lines[1].startswith("- cannot read the run file")
    broken = tmp_path / "broken.json"
    broken.write_text("{")
    assert main(["--run", str(broken), "--history", hist], out=lambda s: None) == 2


def test_only_a_passing_run_is_recorded_in_the_history(tmp_path):
    hist = write(tmp_path, "history.json", BASE)
    quiet = dict(out=lambda s: None)
    assert main(["--run", write(tmp_path, "r.json", RUNS["same"][0]), "--history", hist, "--record"], **quiet) == 0
    assert len(load_history(hist)) == 11
    assert main(["--run", write(tmp_path, "r.json", RUNS["slower"][1]), "--history", hist, "--record"], **quiet) == 1
    busy = {**RUNS["same"][1], "generator_cpu_max": 99}
    assert main(["--run", write(tmp_path, "r.json", busy), "--history", hist, "--record"], **quiet) == 2
    assert len(load_history(hist)) == 11  # the slow run and the invalid run stayed out of the baseline
    assert main(["--run", write(tmp_path, "r.json", RUNS["same"][2]), "--history", hist], **quiet) == 0
    assert len(load_history(hist)) == 11  # without --record nothing is written


def test_a_fresh_real_run_against_a_failing_build_goes_through_the_gate():
    """One real Locust run, a few seconds: the practice API fails 90 % of the payment creations, so the run is a real,
    readable, failing one. The machine-dependent limits are switched off so the verdict does not depend on how busy
    this computer is."""
    run = run_summary("fresh", error_rate=0.9, seconds=3)
    assert set(run) >= {"build", "samples", "errors", "p50_ms", "p95_ms", "p99_ms", "rps", "generator_cpu_max"}
    assert run["samples"] > 0 and run["errors"] > 0
    result = evaluate(run, BASE, min_samples=1, max_cpu=100)
    assert result["code"] == 1
    assert any(r.startswith("error rate") for r in result["reasons"])
