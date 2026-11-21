"""Decide where in the pipeline each security check runs (CI/CD lesson).

Exercise - fill in the TODOs; ``tests/devsecops/test_cicd_plan.py`` checks your work.

A pipeline has four moments (``TRIGGERS`` in ``support/cicd_fixture.py``): the pre-commit hook, the pull-request
stage, the merge stage and the nightly run. Each has a time budget, may or may not have a deployed test environment
(``has_app``), and may or may not be given credentials (``secrets_ok`` - code from a pull request is untrusted, so the
pull-request stage gets none). Each check says how long it takes, whether it needs a running app and whether it needs
credentials.
"""

from __future__ import annotations

from cicd_fixture import TRIGGERS, Check, Trigger


def place(check: Check, triggers: tuple[Trigger, ...] = TRIGGERS) -> Trigger:
    """The EARLIEST trigger that fits ``check``.

    TODO: a trigger fits when ``check.seconds <= trigger.budget_s``, and the trigger has an app if the check needs
    one, and the trigger may hold secrets if the check needs them. When no trigger fits, raise ``ValueError`` with a
    message that contains the check's name.
    """
    raise NotImplementedError("place")


def plan(checks: list[Check], triggers: tuple[Trigger, ...] = TRIGGERS) -> dict[str, list[str]]:
    """``{trigger name: sorted check names}``, with EVERY trigger present as a key, in trigger order.

    TODO: put each check at ``place(check, triggers)``. A check placed at the first trigger (the hook) must ALSO be
    listed at the second (the pull-request stage): a hook can be skipped, the pull-request stage cannot.
    """
    raise NotImplementedError("plan")
