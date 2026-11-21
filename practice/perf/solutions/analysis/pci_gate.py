"""A CI regression gate with three exit codes. (uses ``analysis/pci_baseline.py`` - solve that first)

``evaluate(run, history, ...)`` decides about ONE run summary (see ``pci_baseline``) and returns
``{"code": int, "status": str, "reasons": [str, ...]}`` with these exit codes:

- ``EXIT_PASS = 0``, ``EXIT_REGRESSION = 1``, ``EXIT_INVALID = 2`` - 2 means "this run cannot be judged" (the
  measurement is not trustworthy), which is different from 1, "the build is slower or failing".

Order of the checks:

1. **Validity first.** ``validity_problems(run, min_samples=80, max_cpu=80)`` returns the reasons the run cannot be
   trusted, in this order: ``"only N samples (need M)"`` when ``samples`` is below ``min_samples`` (a missing key
   counts as 0); ``"generator CPU reached P% (limit L%)"`` when ``generator_cpu_max`` is above ``max_cpu`` (a
   missing key counts as 0); ``"p95_ms is missing"``. Any problem gives ``code`` 2, ``status`` ``"invalid"``, the
   problems as ``reasons`` and NO further comparison.
2. **Failure reasons**, collected in this order; any of them gives ``code`` 1 and ``status`` ``"fail"``:
   - ``"error rate R% is above M%"`` when ``errors / samples`` is above ``max_error_rate`` (default 0.01); format R
     and M with ``f"{x:.1%}"``;
   - ``"p95 P ms is above the budget B ms"`` when ``budget_p95`` is given and ``p95_ms`` is above it;
   - ``"p95 P ms is C% above the baseline median M ms (tolerance T%)"`` when ``compare`` says ``"regression"``;
     format C and T with ``f"{x:.1%}"`` of the ``change`` and ``tolerance``. This check needs ``min_runs`` (default
     5) runs of history that have ``p95_ms``; with fewer, skip it.
3. Otherwise ``code`` 0 and ``status`` ``"pass"``. When the history had fewer than ``min_runs`` runs, ``reasons`` is
   ``["building baseline (N of M runs)"]`` (the budget and error checks still ran); otherwise ``[]``.

``main(argv, out=print)`` is the command line: ``--run FILE --history FILE [--budget-p95 MS] [--min-runs N]
[--record]``. It prints ``gate: PASS`` / ``gate: FAIL`` / ``gate: INVALID`` and then one ``- reason`` line each through
``out``, and returns the exit code. A run file that is missing or not valid JSON returns 2 with the reason
``cannot read the run file: ...``. With ``--record`` the run is appended to the history (``save_run``) ONLY when the
code is 0: a failing or invalid run must never become part of the baseline.
"""

from __future__ import annotations

import argparse
import json

from analysis.pci_baseline import baseline, compare, load_history, save_run

EXIT_PASS, EXIT_REGRESSION, EXIT_INVALID = 0, 1, 2


def validity_problems(run, min_samples=80, max_cpu=80):
    problems = []
    samples = run.get("samples", 0)
    if samples < min_samples:
        problems.append(f"only {samples} samples (need {min_samples})")
    cpu = run.get("generator_cpu_max", 0)
    if cpu > max_cpu:
        problems.append(f"generator CPU reached {cpu}% (limit {max_cpu}%)")
    if "p95_ms" not in run:
        problems.append("p95_ms is missing")
    return problems


def evaluate(run, history, budget_p95=None, max_error_rate=0.01, min_runs=5, floor=0.05, k=3.0,
             min_samples=80, max_cpu=80):
    problems = validity_problems(run, min_samples, max_cpu)
    if problems:
        return {"code": EXIT_INVALID, "status": "invalid", "reasons": problems}
    reasons = []
    rate = run.get("errors", 0) / run["samples"]
    if rate > max_error_rate:
        reasons.append(f"error rate {rate:.1%} is above {max_error_rate:.1%}")
    if budget_p95 is not None and run["p95_ms"] > budget_p95:
        reasons.append(f"p95 {run['p95_ms']} ms is above the budget {budget_p95} ms")
    base = baseline(history)
    building = base is None or base["n"] < min_runs
    if not building:
        result = compare(base, run["p95_ms"], floor, k)
        if result["status"] == "regression":
            reasons.append(f"p95 {run['p95_ms']} ms is {result['change']:.1%} above the baseline median "
                           f"{base['median']:g} ms (tolerance {result['tolerance']:.1%})")
    if reasons:
        return {"code": EXIT_REGRESSION, "status": "fail", "reasons": reasons}
    note = []
    if building:
        have = 0 if base is None else base["n"]
        note = [f"building baseline ({have} of {min_runs} runs)"]
    return {"code": EXIT_PASS, "status": "pass", "reasons": note}


def main(argv, out=print):
    parser = argparse.ArgumentParser(prog="pci_gate")
    parser.add_argument("--run", required=True)
    parser.add_argument("--history", required=True)
    parser.add_argument("--budget-p95", type=float, default=None)
    parser.add_argument("--min-runs", type=int, default=5)
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args(argv)
    try:
        with open(args.run) as f:
            run = json.load(f)
    except (OSError, json.JSONDecodeError) as err:
        out("gate: INVALID")
        out(f"- cannot read the run file: {err}")
        return EXIT_INVALID
    result = evaluate(run, load_history(args.history), budget_p95=args.budget_p95, min_runs=args.min_runs)
    out(f"gate: {result['status'].upper()}")
    for reason in result["reasons"]:
        out(f"- {reason}")
    if args.record and result["code"] == EXIT_PASS:
        save_run(args.history, run)
    return result["code"]
