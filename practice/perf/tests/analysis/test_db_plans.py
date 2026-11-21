import pytest
from analysis.db_plans import access_paths, explain, full_scans, index_ddl
from db_fixture import build_db

pytestmark = pytest.mark.exercise

BY_MERCHANT = "SELECT id, amount_cents FROM payments WHERE merchant_id = ?"
BY_MERCHANT_AND_DAY = "SELECT id FROM payments WHERE merchant_id = ? AND created_day >= ?"


@pytest.fixture()
def conn():
    return build_db(merchants=500, payments=20_000)


def test_explain_returns_detail_strings(conn):
    plan = explain(conn, BY_MERCHANT, (7,))
    assert len(plan) == 1
    assert plan[0].lstrip().startswith(("SCAN", "SEARCH"))
    assert "payments" in plan[0]


def test_unindexed_filter_is_a_full_scan(conn):
    assert access_paths(conn, BY_MERCHANT, (7,)) == [("SCAN", "payments", None)]
    assert full_scans(conn, BY_MERCHANT, (7,)) == ["payments"]


def test_the_index_turns_the_scan_into_a_search(conn):
    conn.execute(index_ddl("payments", ["merchant_id"]))
    assert access_paths(conn, BY_MERCHANT, (7,)) == [("SEARCH", "payments", "idx_payments_merchant_id")]
    assert full_scans(conn, BY_MERCHANT, (7,)) == []


def test_index_ddl_puts_equality_columns_before_range_columns():
    assert (
        index_ddl("payments", ["merchant_id"], ["created_day"])
        == "CREATE INDEX idx_payments_merchant_id_created_day ON payments (merchant_id, created_day)"
    )
    assert index_ddl("payments", ["merchant_id", "status"]) == (
        "CREATE INDEX idx_payments_merchant_id_status ON payments (merchant_id, status)"
    )


def test_equality_first_index_narrows_on_both_columns(conn):
    conn.execute(index_ddl("payments", ["merchant_id"], ["created_day"]))
    plan = explain(conn, BY_MERCHANT_AND_DAY, (7, 300))
    assert "merchant_id=? AND created_day>?" in plan[0]


def test_range_first_index_narrows_on_the_range_only(conn):
    conn.execute("CREATE INDEX wrong_order ON payments (created_day, merchant_id)")
    plan = explain(conn, BY_MERCHANT_AND_DAY, (7, 300))
    assert "created_day>?" in plan[0]
    assert "merchant_id=?" not in plan[0]


def test_a_function_on_the_column_defeats_the_index(conn):
    conn.execute(index_ddl("payments", ["merchant_id"]))
    sql = "SELECT id FROM payments WHERE CAST(merchant_id AS TEXT) = ?"
    assert full_scans(conn, sql, ("7",)) == ["payments"]


def test_a_scan_that_walks_an_index_is_still_a_scan(conn):
    conn.execute(index_ddl("payments", ["merchant_id"], ["created_day"]))
    sql = "SELECT merchant_id, created_day FROM payments WHERE created_day = ?"
    kinds = access_paths(conn, sql, (5,))
    assert kinds[0][0] == "SCAN" and kinds[0][2] is not None
    assert full_scans(conn, sql, (5,)) == ["payments"]


def test_lines_that_are_not_scans_or_searches_are_skipped(conn):
    sql = "SELECT id FROM payments WHERE merchant_id = ? ORDER BY amount_cents"
    plan = explain(conn, sql, (7,))
    assert any("TEMP B-TREE" in line for line in plan)
    assert len(access_paths(conn, sql, (7,))) == 1
