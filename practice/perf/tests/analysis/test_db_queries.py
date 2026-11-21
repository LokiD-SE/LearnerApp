import pytest
from analysis.db_queries import latest_payments, latest_payments_n_plus_one, totals_for
from db_fixture import CountingConn, build_db

pytestmark = pytest.mark.exercise


@pytest.fixture(scope="module")
def raw():
    return build_db(merchants=40, payments=3000)


def test_given_version_really_is_n_plus_one(raw):
    conn = CountingConn(raw)
    latest_payments_n_plus_one(conn, 25)
    assert conn.count == 26  # 1 for the payments + 25 for the merchants


def test_latest_payments_returns_the_same_rows(raw):
    expected = latest_payments_n_plus_one(CountingConn(raw), 30)
    assert [tuple(row) for row in latest_payments(CountingConn(raw), 30)] == expected


def test_latest_payments_sends_one_query_whatever_the_limit(raw):
    for limit in (1, 10, 100):
        conn = CountingConn(raw)
        rows = latest_payments(conn, limit)
        assert len(rows) == limit
        assert conn.count == 1


def test_latest_payments_is_newest_first(raw):
    ids = [row[0] for row in latest_payments(CountingConn(raw), 5)]
    assert ids == [3000, 2999, 2998, 2997, 2996]


def test_totals_match_a_query_per_merchant(raw):
    ids = [3, 7, 11, 40]
    totals = totals_for(CountingConn(raw), ids)
    for merchant_id in ids:
        count, total = raw.execute(
            "SELECT count(*), coalesce(sum(amount_cents), 0) FROM payments "
            "WHERE merchant_id = ? AND status = 'captured'",
            (merchant_id,),
        ).fetchone()
        assert totals[merchant_id] == (count, total)


def test_totals_use_one_query_for_many_ids(raw):
    conn = CountingConn(raw)
    totals = totals_for(conn, list(range(1, 41)))
    assert len(totals) == 40
    assert conn.count == 1


def test_totals_ids_are_parameters_not_sql_text(raw):
    conn = CountingConn(raw)
    totals_for(conn, [12345, 67890])
    assert conn.count == 1
    sql = conn.queries[0]
    assert "12345" not in sql and "67890" not in sql
    assert sql.count("?") == 2


def test_merchant_without_captured_payments_is_zero(raw):
    assert totals_for(CountingConn(raw), [999]) == {999: (0, 0)}


def test_empty_list_sends_no_query(raw):
    conn = CountingConn(raw)
    assert totals_for(conn, []) == {}
    assert conn.count == 0
