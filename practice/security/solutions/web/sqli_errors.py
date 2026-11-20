"""Error-based detection: does a single quote make the application show a database error? (WSTG-INPV-05)

The WSTG: "The very first test usually consists of adding a single quote ' ... to the field or parameter
under test", and an application that shows the database's error message makes injection easier to confirm.
When errors are hidden behind a generic 500, the probe can only report an anomaly; boolean probing
(``sqli_detect``) is the way to confirm it.

Signatures are the databases' own error texts, from their documentation or source (see ``SIGNATURES``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

Send = Callable[[str], tuple[int, str]]

# (database, pattern). Sources: SQLite - messages printed by Python 3.12's sqlite3 with SQLite 3.45 (run);
# PostgreSQL - src/backend/parser/scan.l ("unterminated quoted string", "%s at or near"); MySQL - server
# error reference, error 1149 ER_SYNTAX_ERROR; Oracle - ORA-01756 "quoted string not properly
# terminated"; SQL Server - the "Unclosed quotation mark" message quoted in WSTG-INPV-05.
SIGNATURES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("SQLite", re.compile(r"sqlite3\.(?:OperationalError|ProgrammingError)|unrecognized token: |"
                          r"near \"[^\"]*\": syntax error")),
    ("PostgreSQL", re.compile(r"unterminated quoted string at or near|syntax error at or near")),
    ("MySQL", re.compile(r"You have an error in your SQL syntax")),
    ("Oracle", re.compile(r"ORA-01756|quoted string not properly terminated")),
    ("SQL Server", re.compile(r"Unclosed quotation mark")),
)


@dataclass(frozen=True)
class ErrorFinding:
    parameter: str
    kind: str  # "sql-error" (a database error is shown) or "server-error" (only a 5xx; confirm by boolean)
    databases: tuple[str, ...]
    status: int
    evidence: str


def classify(body: str) -> list[str]:
    """Databases whose error signature appears in ``body``, in SIGNATURES order, each once."""
    return [name for name, pattern in SIGNATURES if pattern.search(body)]


def evidence_line(body: str, limit: int = 200) -> str:
    """The first line that matches a signature, stripped and cut to ``limit`` characters ("" if none)."""
    for line in body.splitlines():
        if any(p.search(line) for _, p in SIGNATURES):
            return line.strip()[:limit]
    return ""


def probe_error(send: Send, parameter: str, value: str) -> ErrorFinding | None:
    """Send ``value`` and ``value + "'"``. Report a database error that only the quote produced
    (signatures already on the normal page do not count), else a new 5xx as a "server-error" anomaly."""
    base_status, base_body = send(value)
    status, body = send(value + "'")
    already = set(classify(base_body))
    new = tuple(name for name in classify(body) if name not in already)
    if new:
        return ErrorFinding(parameter, "sql-error", new, status, evidence_line(body))
    if status >= 500 and base_status < 500:
        return ErrorFinding(parameter, "server-error", (), status, f"{value!r} -> {base_status}, {value + chr(39)!r} -> {status}")
    return None
