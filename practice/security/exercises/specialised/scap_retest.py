"""EXERCISE - compare an assessment with its retest, and decide whether the system may be called clean.

NIST SP 800-115 section 8.3: retesting validates a fix, but "the test team will be able to verify its implementation
only if a mirror copy of the original test is performed". Compare flaw by flaw, and treat "could not test it this
time" as its own answer - never as "fixed":

before -> after             outcome
found      -> not-found     fixed
found      -> found         still-open
not-found  -> found         new            (also inconclusive / blocked / not-run / absent before -> found)
not-found  -> not-found     unchanged
other      -> not-found     newly-tested   (it could not be tested before; it is clear now)
anything   -> inconclusive, blocked, not-run, or absent in the retest -> unverified

``Assessment.get(flaw)`` returns the ``Result`` or ``None``.
"""

from __future__ import annotations

from scap_fixture import Assessment, Retest  # noqa: F401

UNTESTED = ("inconclusive", "blocked", "not-run")


def retest(before: Assessment, after: Assessment) -> list[Retest]:
    """One ``Retest(flaw, outcome, note)`` per flaw: the flaws of ``before`` in order, then flaws that appear only in
    ``after``. The note is free text. TODO."""
    raise NotImplementedError("retest")


def clean_bill(after: Assessment, expected: list[str]) -> bool:
    """True only when EVERY flaw in ``expected`` has a result in ``after`` and it is ``not-found``. A missing result,
    an inconclusive one, a blocked one or one that never ran is NOT a pass. TODO."""
    raise NotImplementedError("clean_bill")


def exit_code(outcomes: list[Retest]) -> int:
    """For a pipeline: 1 when any outcome is ``still-open`` or ``new``; otherwise 2 when any is ``unverified``;
    otherwise 0. TODO."""
    raise NotImplementedError("exit_code")
