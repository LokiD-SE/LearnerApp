"""SOLUTION - Turn scan findings into a pipeline verdict, the way ZAP's baseline script and exitStatus job do."""

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
    config: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            raise ValueError(f"bad rule line: {line!r}")
        action = parts[1].strip().upper()
        if action not in ACTIONS:
            raise ValueError(f"unknown action {parts[1]!r} for rule {parts[0]!r}")
        config[parts[0].strip()] = (action, parts[3].strip() if len(parts) > 3 else "")
    return config


def evaluate(findings: list[Finding], config: dict[str, tuple[str, str]], default: str = "WARN") -> GateResult:
    if default not in ACTIONS:
        raise ValueError(f"unknown default action {default!r}")
    result = GateResult()
    for finding in findings:
        rule = plugin_id(finding.rule_id)
        result.outcomes[rule] = config.get(rule, (default, ""))[0]
    for action in result.outcomes.values():
        result.counts[action] += 1
    if result.counts["FAIL"]:
        result.exit_code = 1
    elif result.counts["WARN"]:
        result.exit_code = 2
    return result


def exit_status(
    findings: list[Finding],
    warn_level: str | None = None,
    error_level: str | None = None,
    ok_exit_value: int = 0,
    error_exit_value: int = 1,
    warn_exit_value: int = 2,
) -> int:
    for level in (warn_level, error_level):
        if level is not None and level not in RISKS:
            raise ValueError(f"unknown risk level {level!r}")
    worst = max((RISKS.index(f.risk) for f in findings), default=-1)
    if error_level is not None and worst >= RISKS.index(error_level):
        return error_exit_value
    if warn_level is not None and worst >= RISKS.index(warn_level):
        return warn_exit_value
    return ok_exit_value
