"""Track coverage of a WSTG testing checklist (exercise).

Write every function that raises NotImplementedError; the docstrings say what each must do. Run the
tests with: .venv/bin/python -m pytest tests/foundations/test_wstg_checklist.py

The OWASP Web Security Testing Guide v4.2 ships its checklist as a Markdown table (``checklist/Testing_Checklist.md``)
with the columns Test ID, Test Name, Status and Notes, and says: 'The ``Status`` column can be set for values
similar to "Pass", "Fail", "N/A".' A tester fills in Status as they go; this module reads the table back and
answers "how far are we, and what failed?" per category.

The real table has quirks a parser must survive (see support/wstg_fixture.py): category rows in bold
(``| **WSTG-INFO** | **Information Gathering** | | |``), and two category ids that are not their tests' prefix
(``WSTG-BUSLOGIC`` heads ``WSTG-BUSL-..`` tests, ``WSTG-CLIENT`` heads ``WSTG-CLNT-..``). So the category of a
test comes from its own id, never from the row above it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TEST_ID = re.compile(r"^WSTG-[A-Z]{4}-\d{2}$")
STATUSES = {"pass": "Pass", "fail": "Fail", "n/a": "N/A", "na": "N/A", "": "Not tested"}


@dataclass(frozen=True)
class Item:
    test_id: str
    name: str
    status: str  # "Pass", "Fail", "N/A" or "Not tested"
    notes: str


@dataclass(frozen=True)
class Coverage:
    total: int
    passed: int
    failed: int
    not_applicable: int
    not_tested: int
    percent_done: float  # tests with any status, as a percentage of all tests, rounded to 1 decimal place


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_checklist(markdown: str) -> list[Item]:
    """Every test row of a WSTG checklist table, in order.

    Skips the header row, the ``|---|`` separator, bold category rows and anything that is not a table row.
    Raises ``ValueError`` naming the row for a test id that is not ``WSTG-XXXX-NN`` or an unknown status.
    """
    raise NotImplementedError("TODO: write parse_checklist")


def category_of(test_id: str) -> str:
    """``WSTG-ATHN-03`` -> ``WSTG-ATHN``."""
    raise NotImplementedError("TODO: write category_of")


def coverage(items: list[Item]) -> dict[str, Coverage]:
    """Status counts per category (keyed by ``category_of``), in the order categories first appear."""
    raise NotImplementedError("TODO: write coverage")


def failing(items: list[Item]) -> list[str]:
    """Ids of the tests marked Fail, in checklist order."""
    raise NotImplementedError("TODO: write failing")
