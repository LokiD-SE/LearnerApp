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
    raise NotImplementedError("TODO: the event names, whatever shape and spelling the on key has")


def perf_jobs(workflow):
    raise NotImplementedError("TODO: ids of the jobs with a run step that mentions a performance tool")


def lint(workflow, pr_budget_minutes=15):
    raise NotImplementedError("TODO: the findings, sorted by (job, rule)")
