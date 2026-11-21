"""Exercise: read a query plan and choose an index.

SQLite's ``EXPLAIN QUERY PLAN`` returns rows ``(id, parent, notused, detail)``. The ``detail`` text starts with
``SCAN`` (a full-table scan, "including cases where SQLite iterates through all records in a table in an order
defined by an index") or ``SEARCH`` (only a subset of the rows is visited), for example::

    SCAN payments
    SEARCH payments USING INDEX idx_payments_merchant (merchant_id=?)
    SEARCH payments USING COVERING INDEX idx_b (merchant_id=? AND created_day>?)

Older SQLite versions write ``SCAN TABLE payments``; handle both. This is SQLite's wording - PostgreSQL's
``EXPLAIN`` says ``Seq Scan`` / ``Index Scan`` - but the habit (look for the scan first) is the same.
"""


def explain(conn, sql, params=()):
    """TODO: the ``detail`` strings of ``EXPLAIN QUERY PLAN <sql>``, in the order SQLite returns them."""
    raise NotImplementedError("run EXPLAIN QUERY PLAN and keep the detail column")


def access_paths(conn, sql, params=()):
    """TODO: one ``(kind, table, index)`` tuple per plan line that starts with SCAN or SEARCH.

    ``kind`` is "SCAN" or "SEARCH"; ``table`` is the name (or alias) after it, without a ``TABLE`` word;
    ``index`` is the index name after ``INDEX`` (``USING INDEX x`` or ``USING COVERING INDEX x``), else ``None``.
    Lines that are not SCAN/SEARCH (for example ``USE TEMP B-TREE FOR ORDER BY``) are skipped.
    """
    raise NotImplementedError("parse the plan lines")


def full_scans(conn, sql, params=()):
    """TODO: the tables (or aliases) the query reads with a SCAN - with or without an index - in plan order."""
    raise NotImplementedError("filter access_paths")


def index_ddl(table, equality, range_columns=()):
    """TODO: the ``CREATE INDEX`` statement for a query that filters on ``equality`` columns with ``=`` and on
    ``range_columns`` with ``<``, ``>``, ``BETWEEN``.

    Equality columns come first, then range columns - a column after a range column cannot narrow the search.
    The name is ``idx_<table>_<columns joined by _>``, for example::

        index_ddl("payments", ["merchant_id"], ["created_day"])
        -> "CREATE INDEX idx_payments_merchant_id_created_day ON payments (merchant_id, created_day)"
    """
    raise NotImplementedError("equality columns first")
