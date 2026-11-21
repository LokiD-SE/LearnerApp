"""SOLUTION - Guard a regression test against being flaky, blind or noisy, and decide what CI does with it.

Google's testing blog defines a flaky test result as "a test that exhibits both a passing and a failing result with the
same code". A security regression test has the same disease and a second one: it can be wrong in a way that looks like
success. ``run_guard`` runs a probe several times against ONE vulnerable build and ONE build with only that flaw
fixed, and ``classify`` turns the answers into a verdict:

- ``flaky``: the probe gave both answers on the same build - the test cannot be trusted either way;
- ``noisy``: it reports the flaw on the fixed build - a false positive (the test can never go green);
- ``blind``: it never reports the flaw on the vulnerable build - a false negative (the test is always green);
- ``trustworthy``: it reports the flaw every time on the vulnerable build and never on the fixed one;
- ``broken``: the probe's positive control failed (``RuntimeError``), so there is no answer at all.
"""

from __future__ import annotations

from typing import Callable

from reg_fixture import GuardResult
from sandpay_vuln import make_app, serve


def classify(vulnerable_runs: list[bool] | tuple[bool, ...], fixed_runs: list[bool] | tuple[bool, ...]) -> str:
    """The verdict for the two lists of answers (True = the probe reported the flaw). Both must be non-empty.

    Order of checks: mixed answers on either build -> ``flaky``; flaw reported on the fixed build -> ``noisy``;
    flaw never reported on the vulnerable build -> ``blind``; otherwise ``trustworthy``.
    """
    if not vulnerable_runs or not fixed_runs:
        raise ValueError("need at least one run on each build")
    if len(set(vulnerable_runs)) > 1 or len(set(fixed_runs)) > 1:
        return "flaky"
    if fixed_runs[0]:
        return "noisy"
    if not vulnerable_runs[0]:
        return "blind"
    return "trustworthy"


def run_guard(probe: Callable[[str], bool], flaw: str, runs: int = 5) -> GuardResult:
    """Run ``probe`` ``runs`` times on one vulnerable portal, then ``runs`` times on one with only ``flaw`` fixed.

    ``runs`` below 1 is a ``ValueError``. If the probe raises ``RuntimeError`` (its control failed) the verdict is
    ``broken`` and the answers collected so far are kept.
    """
    if runs < 1:
        raise ValueError("runs must be at least 1")
    answers: dict[str, list[bool]] = {"vulnerable": [], "fixed": []}
    try:
        with serve(make_app()) as base:
            for _ in range(runs):
                answers["vulnerable"].append(bool(probe(base)))
        with serve(make_app({flaw})) as base:
            for _ in range(runs):
                answers["fixed"].append(bool(probe(base)))
    except RuntimeError:
        return GuardResult(flaw, tuple(answers["vulnerable"]), tuple(answers["fixed"]), "broken")
    return GuardResult(flaw, tuple(answers["vulnerable"]), tuple(answers["fixed"]),
                       classify(answers["vulnerable"], answers["fixed"]))


def ci_action(verdict: str, quarantined_days: int = 0, max_days: int = 14) -> str:
    """What the pipeline does with a test of this verdict.

    - ``trustworthy`` -> ``gate`` (a failure blocks the merge);
    - ``flaky`` -> ``quarantine`` (runs, reports, does not block) for up to ``max_days`` days, then ``escalate``
      (blocks again until it is fixed or a named owner accepts the risk in writing);
    - ``blind``, ``noisy`` and ``broken`` -> ``fix-test`` (the test is wrong, never delete the finding's coverage);
    - anything else is a ``ValueError`` - an unknown verdict must not turn into a pass.
    """
    if verdict == "trustworthy":
        return "gate"
    if verdict == "flaky":
        return "quarantine" if quarantined_days <= max_days else "escalate"
    if verdict in ("blind", "noisy", "broken"):
        return "fix-test"
    raise ValueError(f"unknown verdict {verdict!r}")
