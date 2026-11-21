"""SOLUTION - A finding-to-test registry and the checks that keep it honest.

The registry answers one question a year after the assessment: "for each finding we closed, which test stops it coming
back, and does that test still exist?" Each entry has an id, the flaw, a severity, a status (open, fixed, accepted)
and, for a closed finding, the pytest node id of its test.

``registry_problems`` reports five kinds of problem, in this order per entry and then the orphans:

- ``fixed-without-test``: status fixed and no test;
- ``dangling-test``: the entry names a test that pytest did not collect (renamed, deleted or never written);
- ``accepted-incomplete``: status accepted without an ``accepted_until`` date or without a reason;
- ``accepted-expired``: ``accepted_until`` is before today (the accepted day itself is still valid);
- ``orphan-test``: a collected test that no entry names (``finding_id`` is None).
"""

from __future__ import annotations

import json
from datetime import date

from reg_fixture import SEVERITIES, STATUSES, Entry, Problem


def parse_registry(text: str) -> list[Entry]:
    """Parse the registry JSON. Fail closed: a bad registry is an error, never a silently shorter list."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"registry is not valid JSON: {exc.msg}") from exc
    if not isinstance(data, list):
        raise ValueError("registry must be a JSON list")
    entries: list[Entry] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("every registry entry must be an object")
        for key in ("id", "flaw", "severity", "status"):
            if key not in item:
                raise ValueError(f"entry is missing {key!r}")
        if item["status"] not in STATUSES:
            raise ValueError(f"{item['id']}: unknown status {item['status']!r}")
        if item["severity"] not in SEVERITIES:
            raise ValueError(f"{item['id']}: unknown severity {item['severity']!r}")
        if item["id"] in seen:
            raise ValueError(f"duplicate finding id {item['id']!r}")
        seen.add(item["id"])
        entries.append(Entry(item["id"], item["flaw"], item["severity"], item["status"], item.get("test"),
                             item.get("fixed_in"), item.get("accepted_until"), item.get("reason")))
    return entries


def parse_collected(output: str) -> set[str]:
    """The pytest node ids in ``pytest --collect-only -q`` output (one ``path::name`` per line).

    Everything else - the blank line, the "N tests collected" summary, warnings - is ignored. A line is a node id when
    it has no spaces and contains ``::``.
    """
    ids: set[str] = set()
    for raw in output.splitlines():
        line = raw.strip()
        if line and " " not in line and "::" in line:
            ids.add(line)
    return ids


def registry_problems(entries: list[Entry], test_ids: set[str], today: str) -> list[Problem]:
    """All problems of the registry, as described in the module docstring. ``today`` is an ISO date."""
    now = date.fromisoformat(today)
    problems: list[Problem] = []
    for e in entries:
        if e.status == "fixed" and not e.test:
            problems.append(Problem("fixed-without-test", e.id, f"{e.flaw} is fixed but no test guards it"))
        if e.test and e.test not in test_ids:
            problems.append(Problem("dangling-test", e.id, f"{e.test} was not collected"))
        if e.status == "accepted":
            if not e.accepted_until or not e.reason:
                problems.append(Problem("accepted-incomplete", e.id, "an accepted risk needs a date and a reason"))
            elif date.fromisoformat(e.accepted_until) < now:
                problems.append(Problem("accepted-expired", e.id, f"acceptance ended on {e.accepted_until}"))
    named = {e.test for e in entries if e.test}
    for test_id in sorted(test_ids - named):
        problems.append(Problem("orphan-test", None, f"{test_id} guards no registered finding"))
    return problems


def coverage(entries: list[Entry], test_ids: set[str]) -> dict:
    """``{"fixed": n, "covered": n, "ratio": r}``: how many fixed findings have a collected test.

    ``ratio`` is ``covered / fixed`` rounded to 2 places, and 1.0 when nothing is fixed yet (nothing to cover).
    """
    fixed = [e for e in entries if e.status == "fixed"]
    covered = [e for e in fixed if e.test and e.test in test_ids]
    ratio = round(len(covered) / len(fixed), 2) if fixed else 1.0
    return {"fixed": len(fixed), "covered": len(covered), "ratio": ratio}
