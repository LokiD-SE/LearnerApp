"""EXERCISE - A tiny SAST engine: parse Python with ``ast`` and report five risky shapes.

A real tool (Semgrep, CodeQL, Bandit) does this at much larger scale. Here you write the matching yourself, so
you can see exactly why a rule fires on one line and stays quiet on the next.
"""

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


@dataclass(frozen=True)
class Finding:
    rule_id: str
    line: int
    severity: str
    message: str


def scan_source(source: str, path: str = "<string>") -> list[Finding]:
    """Parse ``source`` and return the findings, sorted by (line, rule id). ``Finding.line`` is the line where
    the call starts.

    The five rules (all are about CALLS - walk the tree for ``ast.Call``):

    * ``eval-exec``: a call to the builtin ``eval`` or ``exec`` (not ``ast.literal_eval``).
    * ``sql-built-from-string``: a method named in ``SQL_SINKS`` whose FIRST argument is a string built at run
      time - an f-string with a ``{...}`` part, ``+`` or ``%`` with a non-literal operand, or ``"...".format(x)``
      with a non-literal argument. A plain variable, a literal, or ``"a" + "b"`` (two literals) is NOT a finding.
    * ``shell-true``: ``subprocess.<name>`` for a name in ``SUBPROCESS_CALLS`` with ``shell=True``.
    * ``weak-hash``: ``hashlib.md5`` or ``hashlib.sha1``, unless the call passes ``usedforsecurity=False``
      (a checksum, not a security use).
    * ``tls-verify-off``: any call with the keyword ``verify=False``.

    Use ``RULES[rule_id]`` for the severity and message. A file that does not parse raises
    ``ValueError("cannot parse <path>: ...")`` - a file the scanner could not read must never look clean.
    """
    raise NotImplementedError("TODO: parse with ast, walk the Call nodes, apply the five rules")
