"""EXERCISE - Triage a scanner report before anything is reported or fixed (mock interview).

The debug-style question: "The scanner reported twelve findings. What do you do?" The answer is an ORDER, and the
order carries the ethics: first check that every finding is inside the written scope, then that the test behind a
result worked, then verify what nobody has tried, and only then report. Like the citation check of a RAG triage,
the scope check comes first because nothing after it matters for a target you are not allowed to touch.

A finding is placed in exactly one label of ``smi_fixture.LABELS`` - the first rule that applies wins:

1. ``out_of_scope`` - the host is not in the written scope (whatever else is true of the finding);
2. ``duplicate`` - it repeats another finding (``duplicate_of`` is set);
3. ``unverified`` - nobody has tried to reproduce it (``repro`` is ``"not_tried"``);
4. ``invalid_test`` - it was tried, but the positive control did not work, so neither a hit nor a miss counts;
5. ``confirmed`` - reproduced, with a working control;
6. ``false_positive`` - not reproduced, with a working control (on this build, by this test).
"""

from __future__ import annotations

from typing import Iterable

from smi_fixture import LABELS, NEXT_STEP, REPRO, SEVERITY_ORDER, ScanFinding


def classify(finding: ScanFinding) -> str:
    """The label of one finding, by the first rule of the module docstring that applies.

    Raise ``ValueError`` when ``repro`` is not one of ``REPRO`` or ``claimed`` is not one of ``SEVERITY_ORDER``
    - even for a finding that would be out of scope, so a bad record never slips through quietly.
    """
    raise NotImplementedError("TODO: implement classify")


def triage(findings: Iterable[ScanFinding]) -> dict[str, int]:
    """How many findings fall in each label. Every label of ``LABELS`` is present, with 0 when empty."""
    raise NotImplementedError("TODO: implement triage")


def next_step(counts: dict[str, int]) -> str:
    """What to do next: the ``NEXT_STEP`` text of the FIRST label in ``LABELS`` order that has a count above 0.

    The order of ``LABELS`` is the order of the work: scope problems, then broken tests, then unverified findings,
    then the confirmed ones. Return ``"Nothing to triage."`` when every count is 0 or the dict is empty.
    """
    raise NotImplementedError("TODO: implement next_step")


def report_order(findings: Iterable[ScanFinding]) -> list[str]:
    """The ids of the CONFIRMED findings in the order a report should list them.

    Most severe claim first (``SEVERITY_ORDER``), then by id. Findings with any other label are left out.
    """
    raise NotImplementedError("TODO: implement report_order")
