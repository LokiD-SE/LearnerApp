"""Test data for a CSV Data Set Config: one SandPay merchant per row, and a check that a run used each once.

The practice API (``support/sandpay_target.py``) knows clients ``merchant-1`` .. ``merchant-50`` with secrets
``secret-1`` .. ``secret-50``. ``jm_data_login.jmx`` reads the file this module writes: its CSV Data Set Config
has an empty Variable Names field, so JMeter takes the variable names from the header line - "if the variable
name field empty, then the first line of the file is read and interpreted as the list of column names" (JMeter
component reference, CSV Data Set Config). Each sampler label ends with the merchant that sent it, for example
``POST /auth/token merchant-7``, so the results file shows which row each iteration used.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

HEADER = ("client_id", "client_secret")
KNOWN_CLIENTS = range(1, 51)  # merchant-1 .. merchant-50 exist on the practice API
EOF_VALUE = "<EOF>"  # what CSV Data Set Config puts in every variable at end of file (recycle and stop both off)
LOGIN = "POST /auth/token "


def write_credentials(path: Path, count: int, first: int = 1) -> Path:
    """Writes ``count`` merchants starting at ``merchant-<first>``, header line first; returns ``path``.

    Raises ValueError for a count below 1 or a merchant the practice API does not know.
    """
    if count < 1:
        raise ValueError("count must be at least 1")
    last = first + count - 1
    if first not in KNOWN_CLIENTS or last not in KNOWN_CLIENTS:
        raise ValueError(f"merchants {first}..{last} are not all known to the practice API (1..50)")
    path = Path(path)
    with path.open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(HEADER)
        for n in range(first, last + 1):
            writer.writerow((f"merchant-{n}", f"secret-{n}"))
    return path


def logins_by_client(rows: list[dict[str, str]]) -> Counter:
    """Successful sign-ins per merchant, from JTL rows (``load_tools.read_jtl``): labels ``POST /auth/token <id>``
    with response code 200."""
    return Counter(r["label"][len(LOGIN):] for r in rows
                   if r["label"].startswith(LOGIN) and r["responseCode"] == "200")


def data_problems(rows: list[dict[str, str]]) -> list[str]:
    """What is wrong with how the run used its test data, as sentences (empty when nothing is):

    - a merchant that signed in more than once (``reused merchant-3 (2 sign-ins)``),
    - a sample whose label still holds an undefined variable (``undefined variable in 'POST /auth/token ${client_id}'``),
    - a sample that ran past the end of the file (``end of file reached in 'POST /auth/token <EOF>'``),
    - any failed sample (``failed sample 'GET /v1/payments merchant-2' (401)``).
    One sentence per sample or merchant, in JTL order, duplicates last.
    """
    problems: list[str] = []
    for r in rows:
        label = r["label"]
        if "${" in label:
            problems.append(f"undefined variable in '{label}'")
        elif EOF_VALUE in label:
            problems.append(f"end of file reached in '{label}'")
        elif r["success"] != "true":
            problems.append(f"failed sample '{label}' ({r['responseCode']})")
    for client, n in sorted(logins_by_client(rows).items()):
        if n > 1:
            problems.append(f"reused {client} ({n} sign-ins)")
    return problems
