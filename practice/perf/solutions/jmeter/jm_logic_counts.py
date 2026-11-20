"""Predict how many samples a plan with logic controllers produces, and read Transaction Controller samples.

A load test's mix is decided by its logic controllers, so you should be able to say *before* the run how many
samples of each label it will produce - and check the results file against that prediction afterwards.

The plan is ``jmeter/jm_logic_journey.jmx`` (solved): per thread, sign in once (Once Only Controller), then in
every iteration a "Checkout" Transaction Controller (not parent mode) around POST /v1/payments and
GET /v1/payments/{id}, and a Throughput Controller (percent executions, per user) around
GET /v1/reports/settlement.

How a Throughput Controller in percent mode decides - read from JMeter 5.6.3's ``ThroughputController`` class:
before each pass it runs its children when ``(100 * executions + 50) / (iterations + 1) < percent``, where
``executions`` is how many times it has run so far and ``iterations`` how many passes it has seen so far (both
start at 0; "per user" keeps one pair per thread, otherwise one pair for all threads). It is a deterministic
rule, not a random draw.

Run: .venv/bin/python -m pytest tests/jmeter/test_jm_logic_counts.py
"""

from __future__ import annotations

from collections import Counter

TOKEN, CREATE, FETCH, REPORT, CHECKOUT = ("POST /auth/token", "POST /v1/payments", "GET /v1/payments/{id}",
                                          "GET /v1/reports/settlement", "Checkout")
TRANSACTION_PREFIX = "Number of samples in transaction : "


def throughput_passes(percent: float, iterations: int) -> list[bool]:
    """For a Throughput Controller in percent mode seen ``iterations`` times by one thread (per user), whether
    it runs on each pass: a list of ``iterations`` booleans. Use the rule in the module docstring.
    ValueError for a percent outside 0..100 or negative iterations."""
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    if iterations < 0:
        raise ValueError("iterations must not be negative")
    runs, executions = [], 0
    for seen in range(iterations):
        run = (100 * executions + 50) / (seen + 1) < percent
        runs.append(run)
        executions += run
    return runs


def predict_journey(threads: int, loops: int, report_percent: float) -> Counter:
    """Expected samples per label for the solved journey plan with ``threads`` threads and ``loops``
    iterations each: one sign-in per thread, one payment, one look-up and one "Checkout" transaction sample per
    iteration, and the report on the passes the per-user Throughput Controller allows. Labels with 0 samples
    are left out (a Counter ignores them anyway when compared)."""
    reports = sum(throughput_passes(report_percent, loops))
    counts = Counter({TOKEN: threads, CREATE: threads * loops, FETCH: threads * loops,
                      CHECKOUT: threads * loops, REPORT: threads * reports})
    return +counts


def transaction_report(rows: list[dict[str, str]]) -> dict[str, dict[str, int]]:
    """Per Transaction Controller label, from JTL rows (``load_tools.read_jtl``): ``{"count": n, "failed": f,
    "samples": s, "failing_samples": fs}``. A transaction sample is a row whose responseMessage starts with
    ``"Number of samples in transaction : "`` - for example
    ``"Number of samples in transaction : 2, number of failing samples : 1"``; ``samples`` and
    ``failing_samples`` add up those two numbers over all of the label's transaction rows. ``failed`` counts
    rows with ``success == "false"``. Other rows are ignored."""
    report: dict[str, dict[str, int]] = {}
    for row in rows:
        message = row.get("responseMessage", "")
        if not message.startswith(TRANSACTION_PREFIX):
            continue
        inside, failing = message.removeprefix(TRANSACTION_PREFIX).split(", number of failing samples : ")
        entry = report.setdefault(row["label"], {"count": 0, "failed": 0, "samples": 0, "failing_samples": 0})
        entry["count"] += 1
        entry["failed"] += row["success"] == "false"
        entry["samples"] += int(inside)
        entry["failing_samples"] += int(failing)
    return report
