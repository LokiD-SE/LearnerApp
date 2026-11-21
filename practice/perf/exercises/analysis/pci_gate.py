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

EXIT_PASS, EXIT_REGRESSION, EXIT_INVALID = 0, 1, 2


def validity_problems(run, min_samples=80, max_cpu=80):
    raise NotImplementedError("TODO: the reasons this run cannot be trusted")


def evaluate(run, history, budget_p95=None, max_error_rate=0.01, min_runs=5, floor=0.05, k=3.0,
             min_samples=80, max_cpu=80):
    raise NotImplementedError("TODO: invalid run (2), failure reasons (1), pass (0)")


def main(argv, out=print):
    raise NotImplementedError("TODO: parse the options, evaluate, print, record only a passing run")
