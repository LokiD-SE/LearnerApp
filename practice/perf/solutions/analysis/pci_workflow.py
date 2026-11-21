"""Lint a GitHub Actions workflow for the way it runs performance tests. (no imports needed beyond ``re``)

The workflow arrives as a ``dict`` (the parsed YAML). A **performance job** is a job with a ``run`` step whose text
mentions ``locust``, ``jmeter``, ``k6`` or ``gatling`` as a whole word (any case), or contains ``verify.sh perf``.

1. ``triggers(workflow)`` - the set of event names that start the workflow. The ``on`` key may be a string, a list or
   a mapping (use the keys). YAML 1.1 parsers turn an unquoted ``on`` into ``True``, and a JSON dump of that is the
   string ``"true"``: accept the keys ``"on"``, ``True`` and ``"true"``. No trigger key gives an empty set.
2. ``perf_jobs(workflow)`` - the ids of the performance jobs, in the order they appear.
3. ``lint(workflow, pr_budget_minutes=15)`` - a list of findings ``{"rule", "job", "message"}`` sorted by ``(job, rule)``;
   ``[]`` when there is no performance job. ``job`` is the job id, or ``""`` for a workflow-level finding. The rules:
   - ``no-timeout`` - a performance job without an integer ``timeout-minutes`` (the default is 360 minutes);
   - ``pr-too-long`` - the workflow runs on ``pull_request`` and the job's timeout (360 when it has none) is above
     ``pr_budget_minutes``;
   - ``gate-cannot-fail`` - ``continue-on-error`` is true (``True`` or ``"true"``) on the job, or on a step whose ``run``
     mentions a performance tool, so the gate cannot fail the build (one finding per job);
   - ``no-evidence`` - the job has no ``actions/upload-artifact`` step whose ``if`` contains ``always()`` or
     ``failure()``, so a failing run leaves nothing to read;
   - ``no-concurrency`` - the workflow is triggered by something other than ``pull_request`` and neither the workflow
     nor the job sets ``concurrency``, so two runs can overlap on a shared environment;
   - ``schedule-on-the-hour`` (workflow level, only when there is a performance job) - a ``schedule`` cron entry
     whose minute field is ``0`` or ``00``; GitHub documents that scheduled runs can be delayed at the start of
     every hour.
"""

from __future__ import annotations

import re

MARKERS = re.compile(r"\b(locust|jmeter|k6|gatling)\b|verify\.sh perf", re.IGNORECASE)


def triggers(workflow):
    value = None
    for key in ("on", True, "true"):
        if key in workflow:
            value = workflow[key]
            break
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return set(value)
    return set(value)


def _runs(step):
    return isinstance(step.get("run"), str) and bool(MARKERS.search(step["run"]))


def perf_jobs(workflow):
    return [job_id for job_id, job in workflow.get("jobs", {}).items()
            if any(_runs(step) for step in job.get("steps", []))]


def _true(value):
    return value is True or value == "true"


def lint(workflow, pr_budget_minutes=15):
    jobs = perf_jobs(workflow)
    if not jobs:
        return []
    events = triggers(workflow)
    findings = []

    def add(rule, job, message):
        findings.append({"rule": rule, "job": job, "message": message})

    for job_id in jobs:
        job = workflow["jobs"][job_id]
        steps = job.get("steps", [])
        timeout = job.get("timeout-minutes")
        has_timeout = isinstance(timeout, int) and not isinstance(timeout, bool)
        if not has_timeout:
            add("no-timeout", job_id, "no timeout-minutes; the default is 360 minutes")
        effective = timeout if has_timeout else 360
        if "pull_request" in events and effective > pr_budget_minutes:
            add("pr-too-long", job_id, f"runs on pull_request with a {effective}-minute timeout "
                f"(budget {pr_budget_minutes})")
        if _true(job.get("continue-on-error")) or any(_true(s.get("continue-on-error")) and _runs(s) for s in steps):
            add("gate-cannot-fail", job_id, "continue-on-error lets the performance step fail without failing the build")
        if not any(str(s.get("uses", "")).startswith("actions/upload-artifact")
                   and ("always()" in str(s.get("if", "")) or "failure()" in str(s.get("if", "")))
                   for s in steps):
            add("no-evidence", job_id, "no upload-artifact step that runs when the job fails")
        if events - {"pull_request"} and "concurrency" not in workflow and "concurrency" not in job:
            add("no-concurrency", job_id, "no concurrency group; two runs can overlap on a shared environment")

    schedule = workflow.get("on", workflow.get(True, workflow.get("true")))
    entries = schedule.get("schedule", []) if isinstance(schedule, dict) else []
    for entry in entries or []:
        cron = str(entry.get("cron", "")).split()
        if cron and cron[0] in ("0", "00"):
            add("schedule-on-the-hour", "", f"cron '{' '.join(cron)}' starts on the hour, when scheduled runs can be delayed")
    return sorted(findings, key=lambda f: (f["job"], f["rule"]))
