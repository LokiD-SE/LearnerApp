"""Track coverage of a WSTG testing checklist (reference solution).

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
    items: list[Item] = []
    for number, line in enumerate(markdown.splitlines(), start=1):
        if not line.strip().startswith("|"):
            continue
        cells = _cells(line)
        first = cells[0]
        if first in ("Test ID", "") or set(first) <= set("-: ") or first.startswith("**"):
            continue
        if not TEST_ID.match(first):
            raise ValueError(f"line {number}: {first!r} is not a WSTG test id (WSTG-XXXX-NN)")
        cells += [""] * (4 - len(cells))
        status_key = cells[2].lower()
        if status_key not in STATUSES:
            raise ValueError(f"line {number}: unknown status {cells[2]!r} for {first}")
        items.append(Item(first, cells[1], STATUSES[status_key], cells[3]))
    return items


def category_of(test_id: str) -> str:
    """``WSTG-ATHN-03`` -> ``WSTG-ATHN``."""
    if not TEST_ID.match(test_id):
        raise ValueError(f"{test_id!r} is not a WSTG test id")
    return test_id.rsplit("-", 1)[0]


def coverage(items: list[Item]) -> dict[str, Coverage]:
    """Status counts per category (keyed by ``category_of``), in the order categories first appear."""
    groups: dict[str, list[Item]] = {}
    for item in items:
        groups.setdefault(category_of(item.test_id), []).append(item)
    result: dict[str, Coverage] = {}
    for category, group in groups.items():
        count = {s: sum(1 for i in group if i.status == s) for s in ("Pass", "Fail", "N/A", "Not tested")}
        done = len(group) - count["Not tested"]
        result[category] = Coverage(len(group), count["Pass"], count["Fail"], count["N/A"], count["Not tested"],
                                    round(100 * done / len(group), 1))
    return result


def failing(items: list[Item]) -> list[str]:
    """Ids of the tests marked Fail, in checklist order."""
    return [i.test_id for i in items if i.status == "Fail"]
