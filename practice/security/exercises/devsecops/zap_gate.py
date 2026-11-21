"""Turn scan findings into a pipeline verdict, the way ZAP's baseline script and exitStatus job do (DAST lesson).

Exercise - fill in the TODOs; ``tests/devsecops/test_zap_gate.py`` checks your work.

Two documented behaviours of ZAP:

1. The Docker baseline script reads a rule configuration file: one rule per line, ``<id><TAB><ACTION>`` plus an
   optional ``<TAB>(name)`` and then ``<TAB>message``; lines starting with ``#`` are comments; "only the rule
   identifiers are used". ACTION is ``FAIL``, ``WARN``, ``INFO`` or ``IGNORE``. By default every alert is a WARN. The
   script exits ``0`` (success), ``1`` (at least one FAIL), ``2`` (at least one WARN and no FAIL).
2. The Automation Framework ``exitStatus`` job sets the exit code from risk levels: with ``errorLevel`` or
   ``warnLevel`` set, an alert of that risk "or greater" makes the plan report an error / a warning; the default
   exit values are ``0`` ok, ``1`` error, ``2`` warning (``okExitValue``, ``errorExitValue``, ``warnExitValue``).

The config id is the rule's PLUGIN id: an alert reference like ``10038-1`` is the rule id ``10038`` plus a dash and
the alert type, so ``plugin_id("10038-1") == "10038"``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from zap_fixture import RISKS, Finding

ACTIONS = ("FAIL", "WARN", "INFO", "IGNORE")


@dataclass
class GateResult:
    outcomes: dict[str, str] = field(default_factory=dict)  # plugin id -> action
    counts: dict[str, int] = field(default_factory=lambda: {a: 0 for a in ACTIONS})
    exit_code: int = 0


def plugin_id(rule_id: str) -> str:
    return rule_id.split("-", 1)[0]


def parse_rule_config(text: str) -> dict[str, tuple[str, str]]:
    """``{rule id: (ACTION, message)}`` from a baseline-style config file; message is ``""`` when absent.

    TODO: skip blank lines and ``#`` comments; split a line on tabs (column 0 id, column 1 action, column 3 the
    message); upper-case the action. A line with fewer than two columns, or an action not in ``ACTIONS``, is a
    ``ValueError`` - a typo in a gate must not silently weaken it.
    """
    raise NotImplementedError("parse_rule_config")


def evaluate(findings: list[Finding], config: dict[str, tuple[str, str]], default: str = "WARN") -> GateResult:
    """The verdict for ``findings``: one action per RULE that fired, rule counts per action, and the exit code.

    TODO: an unknown ``default`` is a ``ValueError``. For each finding look up ``plugin_id(rule_id)`` in the config,
    falling back to ``default``; many findings of one rule count once. ``exit_code`` is 1 with any FAIL rule, else 2
    with any WARN rule, else 0 (INFO and IGNORE never fail a pipeline).
    """
    raise NotImplementedError("evaluate")


def exit_status(
    findings: list[Finding],
    warn_level: str | None = None,
    error_level: str | None = None,
    ok_exit_value: int = 0,
    error_exit_value: int = 1,
    warn_exit_value: int = 2,
) -> int:
    """The exit code of an ``exitStatus`` job.

    TODO: a level that is not in ``RISKS`` is a ``ValueError``. Find the highest risk among the findings. Return
    ``error_exit_value`` if ``error_level`` is set and some finding has that risk or greater, else
    ``warn_exit_value`` if ``warn_level`` is set and some finding has that risk or greater, else ``ok_exit_value``.
    """
    raise NotImplementedError("exit_status")
