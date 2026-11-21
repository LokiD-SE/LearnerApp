"""SOLUTION - compare an assessment with its retest, and decide whether the system may be called clean.

NIST SP 800-115 section 8.3: retesting validates a fix, but "the test team will be able to verify its implementation
only if a mirror copy of the original test is performed". The comparison therefore works flaw by flaw, and it treats
"could not test it this time" as its own answer - never as "fixed":

before -> after             outcome
found      -> not-found     fixed
found      -> found         still-open
not-found  -> found         new            (also: inconclusive/blocked/not-run/absent before -> found)
not-found  -> not-found     unchanged
other      -> not-found     newly-tested   (it could not be tested before, and it is clear now)
anything   -> inconclusive, blocked, not-run, or absent in the retest -> unverified
"""

from __future__ import annotations

from scap_fixture import Assessment, Retest

UNTESTED = ("inconclusive", "blocked", "not-run")


def retest(before: Assessment, after: Assessment) -> list[Retest]:
    """One ``Retest`` per flaw: the flaws of ``before`` in order, then flaws that appear only in ``after``."""
    flaws = [r.flaw for r in before.results]
    flaws += [r.flaw for r in after.results if r.flaw not in flaws]
    out = []
    for flaw in flaws:
        b, a = before.get(flaw), after.get(flaw)
        b_status = b.status if b else "absent"
        if a is None or a.status in UNTESTED:
            outcome, note = "unverified", f"the retest has no usable answer ({'absent' if a is None else a.status}); it was {b_status} before"
        elif a.status == "found":
            outcome = "still-open" if b_status == "found" else "new"
            note = "found again" if outcome == "still-open" else f"found now; it was {b_status} before"
        elif b_status == "found":
            outcome, note = "fixed", "found before, not found now (the control worked)"
        elif b_status == "not-found":
            outcome, note = "unchanged", "not found before or now"
        else:
            outcome, note = "newly-tested", f"it was {b_status} before and is clear now"
        out.append(Retest(flaw, outcome, note))
    return out


def clean_bill(after: Assessment, expected: list[str]) -> bool:
    """True only when EVERY flaw in ``expected`` has a result in ``after`` and that result is ``not-found``.

    A missing result, an inconclusive one, a blocked one or one that never ran is NOT a pass: absence of evidence is
    not evidence of absence.
    """
    for flaw in expected:
        r = after.get(flaw)
        if r is None or r.status != "not-found":
            return False
    return True


def exit_code(outcomes: list[Retest]) -> int:
    """For a pipeline: 1 when anything is ``still-open`` or ``new``; else 2 when anything is ``unverified``; else 0."""
    kinds = {o.outcome for o in outcomes}
    if kinds & {"still-open", "new"}:
        return 1
    if "unverified" in kinds:
        return 2
    return 0
