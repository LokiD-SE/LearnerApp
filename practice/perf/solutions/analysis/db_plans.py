"""Solution: read a query plan and choose an index."""

import re

_PATH = re.compile(r"^(SCAN|SEARCH)\s+(?:TABLE\s+)?(\S+)(?:\s+AS\s+\S+)?(.*)$")
_INDEX = re.compile(r"USING (?:COVERING )?INDEX (\S+)")


def explain(conn, sql, params=()):
    return [row[3] for row in conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()]


def access_paths(conn, sql, params=()):
    paths = []
    for detail in explain(conn, sql, params):
        match = _PATH.match(detail)
        if not match:
            continue
        kind, table, rest = match.groups()
        index = _INDEX.search(rest)
        paths.append((kind, table, index.group(1) if index else None))
    return paths


def full_scans(conn, sql, params=()):
    return [table for kind, table, _ in access_paths(conn, sql, params) if kind == "SCAN"]


def index_ddl(table, equality, range_columns=()):
    columns = [*equality, *range_columns]
    return f"CREATE INDEX idx_{table}_{'_'.join(columns)} ON {table} ({', '.join(columns)})"
