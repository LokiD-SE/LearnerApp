"""Guard a regression test against being flaky, blind or noisy, and decide what CI does with it (regression lesson).

Exercise - fill in the TODOs; ``tests/devsecops/test_reg_guard.py`` checks your work.

Google's testing blog defines a flaky test result as "a test that exhibits both a passing and a failing result with the
same code". ``run_guard`` runs a probe several times on ONE vulnerable build and ONE build with only that flaw fixed;
``classify`` turns the answers (True = the probe reported the flaw) into a verdict:

- ``flaky``: both answers on the same build; ``noisy``: it reports the flaw on the fixed build (false positive);
- ``blind``: it never reports the flaw on the vulnerable build (false negative); ``trustworthy``: every answer is right;
- ``broken``: the probe's positive control failed (``RuntimeError``) - no answer at all.

Check order in ``classify``: mixed answers on either build -> flaky; flaw reported on the fixed build -> noisy; flaw never
reported on the vulnerable build -> blind; otherwise trustworthy. An empty list is a ``ValueError``.

``ci_action(verdict, quarantined_days=0, max_days=14)``: ``trustworthy`` -> ``gate``; ``flaky`` -> ``quarantine`` while
``quarantined_days <= max_days``, then ``escalate``; ``blind``, ``noisy``, ``broken`` -> ``fix-test``; an unknown verdict is
a ``ValueError`` (it must not turn into a pass).
"""

from __future__ import annotations

from typing import Callable

from reg_fixture import GuardResult
from sandpay_vuln import make_app, serve


def classify(vulnerable_runs: list[bool] | tuple[bool, ...], fixed_runs: list[bool] | tuple[bool, ...]) -> str:
    """The verdict for the two lists of answers.

    TODO: the four checks in the order the module docstring gives.
    """
    raise NotImplementedError("classify")


def run_guard(probe: Callable[[str], bool], flaw: str, runs: int = 5) -> GuardResult:
    """Run ``probe`` ``runs`` times on one vulnerable portal, then ``runs`` times on one with only ``flaw`` fixed.

    TODO: ``runs < 1`` is a ``ValueError``; serve each portal ONCE and loop inside; a ``RuntimeError`` from the probe
    gives verdict ``broken`` with the answers collected so far; otherwise ``classify`` them.
    """
    raise NotImplementedError("run_guard")


def ci_action(verdict: str, quarantined_days: int = 0, max_days: int = 14) -> str:
    """What the pipeline does with a test of this verdict.

    TODO: the table in the module docstring; raise ``ValueError`` for an unknown verdict.
    """
    raise NotImplementedError("ci_action")
