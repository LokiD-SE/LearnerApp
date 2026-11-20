"""The fix for SQL injection: bind every data value, allow-list everything structural.

The OWASP SQL Injection Prevention Cheat Sheet: "define the SQL structure separately from its data values,
then bind those values through the database API" - parameterised queries for values, and "fixed
application-owned choices for dynamic table names, column names, sort order (ASC, DESC)", because
placeholders stand for values only. Python's sqlite3 uses ``?`` (qmark) or ``:name`` placeholders.

``find_payments_unsafe`` is the vulnerable original, kept for comparison. ``find_payments`` is the fix.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Sequence

COLUMNS = "id, merchant_id, amount_minor, currency, status"

# Structural choices the caller may make, mapped to fixed SQL text the application owns.
SORT_COLUMNS = {"id": "id", "amount": "amount_minor", "status": "status"}
DIRECTIONS = {"asc": "ASC", "desc": "DESC"}


def find_payments_unsafe(con: sqlite3.Connection, merchant_id: str, status: str) -> list[dict[str, Any]]:
    """VULNERABLE - user input concatenated into SQL. Do not copy."""
    sql = f"SELECT {COLUMNS} FROM payments WHERE merchant_id = '{merchant_id}' AND status = '{status}' ORDER BY id"
    return _rows(con.execute(sql))


def _rows(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def find_payments(con: Any, merchant_id: str, statuses: Sequence[str] | None = None, sort: str = "id",
                  direction: str = "asc") -> list[dict[str, Any]]:
    """Payments of one merchant, optionally only some statuses, sorted by an allowed column.

    - ``merchant_id`` and every status are bound with ``?`` - never part of the SQL text.
    - ``statuses`` becomes ``IN (?, ?, ...)`` with one placeholder per value; an empty list matches
      nothing, so no query is sent.
    - ``sort`` and ``direction`` are looked up in fixed maps; anything else raises ValueError.
    """
    if sort not in SORT_COLUMNS:
        raise ValueError(f"sort must be one of {sorted(SORT_COLUMNS)}")
    if not isinstance(direction, str) or direction.lower() not in DIRECTIONS:
        raise ValueError("direction must be asc or desc")
    params: list[Any] = [merchant_id]
    sql = f"SELECT {COLUMNS} FROM payments WHERE merchant_id = ?"
    if statuses is not None:
        statuses = list(statuses)
        if not statuses:
            return []
        sql += " AND status IN (" + ", ".join("?" for _ in statuses) + ")"
        params.extend(statuses)
    # Both pieces come from the maps above, never from the caller's text.
    sql += f" ORDER BY {SORT_COLUMNS[sort]} {DIRECTIONS[direction.lower()]}, id ASC"
    return _rows(con.execute(sql, params))
