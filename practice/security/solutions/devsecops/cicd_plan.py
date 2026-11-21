"""Decide where in the pipeline each security check runs (CI/CD lesson).

Solution. Each check goes to the EARLIEST trigger where all three are true: it fits the time budget, the trigger has
a running app if the check needs one, and the trigger may hold credentials if the check needs them. A check that runs
in the pre-commit hook also runs in the pull-request stage, because a hook can be skipped and the pull-request stage
cannot.
"""

from __future__ import annotations

from cicd_fixture import TRIGGERS, Check, Trigger


def place(check: Check, triggers: tuple[Trigger, ...] = TRIGGERS) -> Trigger:
    """The earliest trigger that fits ``check``; a ``ValueError`` that names the check when none does."""
    for trigger in triggers:
        if check.seconds > trigger.budget_s:
            continue
        if check.needs_app and not trigger.has_app:
            continue
        if check.needs_secrets and not trigger.secrets_ok:
            continue
        return trigger
    raise ValueError(f"no trigger fits check {check.name!r}: split it, speed it up or add a slower trigger")


def plan(checks: list[Check], triggers: tuple[Trigger, ...] = TRIGGERS) -> dict[str, list[str]]:
    """``{trigger name: sorted check names}`` with every trigger present, in trigger order.

    A check placed at the FIRST trigger is repeated at the second (the hook is not the control).
    """
    result: dict[str, list[str]] = {t.name: [] for t in triggers}
    for check in checks:
        placed = place(check, triggers)
        result[placed.name].append(check.name)
        if placed is triggers[0] and len(triggers) > 1:
            result[triggers[1].name].append(check.name)
    return {name: sorted(names) for name, names in result.items()}
