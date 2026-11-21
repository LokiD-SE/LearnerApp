"""SOLUTION - A tiny SAST engine: parse Python with ``ast`` and report five risky shapes."""

from __future__ import annotations

import ast
from dataclasses import dataclass

# rule id -> (severity, message). Same ids and severities as a Semgrep rule file would carry.
RULES = {
    "eval-exec": ("HIGH", "eval/exec runs text as code"),
    "sql-built-from-string": ("HIGH", "SQL built by string formatting; pass parameters instead"),
    "shell-true": ("HIGH", "shell=True hands the command to a shell; pass an argument list"),
    "weak-hash": ("MEDIUM", "MD5 and SHA-1 are not for passwords or signatures"),
    "tls-verify-off": ("HIGH", "verify=False turns off certificate checking"),
}
SQL_SINKS = {"execute", "executemany", "executescript", "query", "raw"}
SUBPROCESS_CALLS = {"run", "call", "Popen", "check_call", "check_output", "getoutput", "getstatusoutput"}
DYNAMIC_PARTS = (ast.Name, ast.Attribute, ast.Call, ast.Subscript)


@dataclass(frozen=True)
class Finding:
    rule_id: str
    line: int
    severity: str
    message: str


def _is_dynamic_string(node: ast.AST) -> bool:
    """True for a string BUILT from something that is not a literal: f-string, +, % or .format."""
    if isinstance(node, ast.JoinedStr):
        return any(isinstance(part, ast.FormattedValue) for part in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return any(isinstance(n, DYNAMIC_PARTS) for n in ast.walk(node))
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format"
            and isinstance(node.func.value, ast.Constant) and isinstance(node.func.value.value, str)):
        parts = [*node.args, *(k.value for k in node.keywords)]
        return any(not isinstance(p, ast.Constant) for p in parts)
    return False


def _keyword(call: ast.Call, name: str):
    return next((k.value for k in call.keywords if k.arg == name), None)


def _is_constant(node, value) -> bool:
    return isinstance(node, ast.Constant) and node.value is value


def _match(call: ast.Call) -> list[str]:
    func = call.func
    hits = []
    if isinstance(func, ast.Name) and func.id in ("eval", "exec"):
        hits.append("eval-exec")
    if isinstance(func, ast.Attribute):
        if func.attr in SQL_SINKS and call.args and _is_dynamic_string(call.args[0]):
            hits.append("sql-built-from-string")
        base = func.value.id if isinstance(func.value, ast.Name) else None
        if base == "subprocess" and func.attr in SUBPROCESS_CALLS and _is_constant(_keyword(call, "shell"), True):
            hits.append("shell-true")
        if base == "hashlib" and func.attr in ("md5", "sha1") \
                and not _is_constant(_keyword(call, "usedforsecurity"), False):
            hits.append("weak-hash")
    if _is_constant(_keyword(call, "verify"), False):
        hits.append("tls-verify-off")
    return hits


def scan_source(source: str, path: str = "<string>") -> list[Finding]:
    """Parse ``source`` and return the findings, sorted by (line, rule id).

    An unparseable file raises ``ValueError("cannot parse <path>: ...")`` - a file the scanner could not read
    must never look clean.
    """
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as err:
        raise ValueError(f"cannot parse {path}: {err.msg} (line {err.lineno})") from err
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for rule_id in _match(node):
                severity, message = RULES[rule_id]
                findings.append(Finding(rule_id, node.lineno, severity, message))
    return sorted(findings, key=lambda f: (f.line, f.rule_id))
