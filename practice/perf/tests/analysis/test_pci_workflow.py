"""Checks exercises/analysis/pci_workflow.py: a linter for how a GitHub Actions workflow runs performance tests.

The workflows are dicts (parsed YAML). The real one is the repository's own .github/workflows/pages.yml, converted to
support/pci_data/pages.workflow.json on 21 November 2026."""

import pytest
from analysis.pci_workflow import lint, perf_jobs, triggers
from pci_fixture import load_workflow

pytestmark = pytest.mark.exercise

UPLOAD = {"uses": "actions/upload-artifact@v4", "if": "${{ always() }}", "with": {"path": "results"}}


def perf_job(**extra):
    steps = [{"uses": "actions/checkout@v4"}, {"run": "locust -f locustfile.py --headless -u 20 -t 2m"}, UPLOAD]
    return {"runs-on": "ubuntu-latest", "timeout-minutes": 30, **extra, "steps": extra.get("steps", steps)}


def workflow(on, jobs, **extra):
    return {"name": "perf", "on": on, "jobs": jobs, **extra}


NIGHTLY = {"schedule": [{"cron": "17 2 * * *"}], "workflow_dispatch": None}


def rules(findings):
    return [(f["rule"], f["job"]) for f in findings]


def test_triggers_accepts_a_string_a_list_and_a_mapping():
    assert triggers({"on": "push"}) == {"push"}
    assert triggers({"on": ["push", "pull_request"]}) == {"push", "pull_request"}
    assert triggers({"on": {"push": {"branches": ["main"]}, "workflow_dispatch": None}}) == {"push", "workflow_dispatch"}
    assert triggers({"jobs": {}}) == set()


def test_triggers_survives_the_yaml_1_1_spelling_of_on():
    assert triggers({True: {"push": None}}) == {"push"}  # an unquoted on parsed as a boolean
    assert triggers({"true": ["schedule"]}) == {"schedule"}  # the same, after a JSON dump


def test_perf_jobs_look_for_a_performance_tool_in_the_run_steps():
    jobs = {
        "unit": {"steps": [{"run": "npm test"}]},
        "load": {"steps": [{"run": "JMeter -n -t plan.jmx"}]},
        "k6": {"steps": [{"name": "locust", "uses": "grafana/k6-action@v0.3.1"}]},  # a name or uses is not a run step
        "all": {"steps": [{"run": "practice/verify.sh perf"}]},
        "sec": {"steps": [{"run": "practice/verify.sh security"}]},
        "word": {"steps": [{"run": "echo hawk6 flocusts"}]},
        "gat": {"steps": [{"run": "mvn gatling:test"}]},
    }
    assert perf_jobs({"jobs": jobs}) == ["load", "all", "gat"]
    assert perf_jobs({"on": "push"}) == []


def test_a_well_behaved_nightly_job_has_no_findings():
    assert lint(workflow(NIGHTLY, {"load": perf_job()}, concurrency={"group": "perf"})) == []
    assert lint(workflow("push", {"unit": {"steps": [{"run": "npm test"}]}})) == []


def test_a_job_without_a_timeout_runs_up_to_six_hours():
    job = perf_job()
    del job["timeout-minutes"]
    assert rules(lint(workflow(NIGHTLY, {"load": job}, concurrency={"group": "perf"}))) == [("no-timeout", "load")]
    job["timeout-minutes"] = "${{ vars.PERF_MINUTES }}"  # not an integer we can check
    assert rules(lint(workflow(NIGHTLY, {"load": job}, concurrency={"group": "perf"}))) == [("no-timeout", "load")]


def test_a_long_performance_job_does_not_belong_on_every_pull_request():
    pr = {"pull_request": None}
    assert lint(workflow(pr, {"load": perf_job(**{"timeout-minutes": 10})})) == []
    found = lint(workflow(pr, {"load": perf_job(**{"timeout-minutes": 40})}))
    assert rules(found) == [("pr-too-long", "load")]
    assert "40" in found[0]["message"] and "15" in found[0]["message"]
    assert lint(workflow(pr, {"load": perf_job(**{"timeout-minutes": 40})}), pr_budget_minutes=45) == []
    nolimit = perf_job()
    del nolimit["timeout-minutes"]
    assert rules(lint(workflow(pr, {"load": nolimit}))) == [("no-timeout", "load"), ("pr-too-long", "load")]


def test_continue_on_error_makes_a_gate_that_cannot_fail():
    step = {"run": "locust -f locustfile.py --headless", "continue-on-error": True}
    job = perf_job(steps=[step, UPLOAD])
    assert rules(lint(workflow(NIGHTLY, {"load": job}, concurrency={"group": "perf"}))) == [("gate-cannot-fail", "load")]
    on_other_step = perf_job(steps=[{"run": "locust -f f.py"}, {**UPLOAD, "continue-on-error": "true"}])
    assert lint(workflow(NIGHTLY, {"load": on_other_step}, concurrency={"group": "perf"})) == []  # not the gate step
    whole_job = perf_job(**{"continue-on-error": "true"})
    assert rules(lint(workflow(NIGHTLY, {"load": whole_job}, concurrency={"group": "perf"}))) == [("gate-cannot-fail", "load")]


def test_evidence_must_be_uploaded_when_the_job_fails():
    plain_run = [{"run": "locust -f locustfile.py"}]
    only_on_success = plain_run + [{"uses": "actions/upload-artifact@v4"}]
    on_failure = plain_run + [{"uses": "actions/upload-artifact@v4", "if": "failure()"}]
    other_action = plain_run + [{"uses": "actions/cache@v4", "if": "always()"}]
    for steps, expected in ((plain_run, True), (only_on_success, True), (other_action, True), (on_failure, False)):
        found = lint(workflow(NIGHTLY, {"load": perf_job(steps=steps)}, concurrency={"group": "perf"}))
        assert (rules(found) == [("no-evidence", "load")]) is expected


def test_overlapping_runs_need_a_concurrency_group_unless_it_is_pull_request_only():
    wf = workflow(NIGHTLY, {"load": perf_job()})
    assert rules(lint(wf)) == [("no-concurrency", "load")]
    assert lint(workflow(NIGHTLY, {"load": perf_job(concurrency="perf-env")})) == []  # job level counts
    assert lint({**wf, "concurrency": {"group": "perf"}}) == []  # workflow level counts
    assert lint(workflow({"pull_request": None}, {"load": perf_job(**{"timeout-minutes": 10})})) == []


def test_a_schedule_on_the_hour_is_flagged_once_for_the_workflow():
    for cron, flagged in (("0 2 * * *", True), ("00 3 * * 1", True), ("30 2 * * *", False), ("*/15 * * * *", False)):
        wf = workflow({"schedule": [{"cron": cron}]}, {"load": perf_job()}, concurrency={"group": "perf"})
        assert (rules(lint(wf)) == [("schedule-on-the-hour", "")]) is flagged
    both = workflow({"schedule": [{"cron": "0 1 * * *"}, {"cron": "0 13 * * *"}]}, {"a": perf_job(), "b": perf_job()},
                    concurrency={"group": "perf"})
    assert [f["rule"] for f in lint(both)].count("schedule-on-the-hour") == 2  # one per cron entry, not per job
    no_perf = workflow({"schedule": [{"cron": "0 1 * * *"}]}, {"unit": {"steps": [{"run": "npm test"}]}})
    assert lint(no_perf) == []


def test_findings_are_sorted_by_job_then_rule():
    wf = workflow(["push", "pull_request"], {"z": perf_job(**{"timeout-minutes": 60}), "a": perf_job(steps=[{"run": "k6 run t.js"}])})
    got = rules(lint(wf))
    assert got == sorted(got, key=lambda r: (r[1], r[0]))
    assert got[0][1] == "a" and got[-1][1] == "z"


def test_the_repositorys_own_workflow_has_one_finding():
    wf = load_workflow("pages.workflow")
    assert triggers(wf) == {"push", "pull_request", "workflow_dispatch"}
    assert perf_jobs(wf) == ["practice"]  # it runs `practice/verify.sh perf` among the other practice projects
    found = lint(wf)
    assert rules(found) == [("pr-too-long", "practice")]
    assert "40-minute" in found[0]["message"]
    assert lint(wf, pr_budget_minutes=45) == []
