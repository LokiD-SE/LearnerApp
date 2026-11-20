import sqlite3

import pytest
from web.sqli_safe_query import find_payments, find_payments_unsafe

pytestmark = pytest.mark.exercise

ROWS = [
    ("pay_1001", "m_100", 2500, "EUR", "captured"),
    ("pay_1002", "m_100", 990, "EUR", "refunded"),
    ("pay_1003", "m_100", 12000, "GBP", "authorized"),
    ("pay_1004", "m_100", 700, "EUR", "o'brien-hold"),  # a legitimate value with a quote in it
    ("pay_2001", "m_200", 4999, "EUR", "captured"),
]

ATTACKS = [
    "x' OR '1'='1",
    "captured' AND '1'='1",
    "captured'; DROP TABLE payments; --",
    "' UNION SELECT id, merchant_id, amount_minor, currency, status FROM payments --",
    "captured' --",
]


class RecordingConnection:
    """Wraps a sqlite3 connection and records every execute(sql, params) the code under test makes."""

    def __init__(self, con):
        self.con, self.calls = con, []

    def execute(self, sql, params=()):
        self.calls.append((sql, tuple(params)))
        return self.con.execute(sql, params)


@pytest.fixture
def db():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE payments (id TEXT, merchant_id TEXT, amount_minor INTEGER, currency TEXT, status TEXT)")
    con.executemany("INSERT INTO payments VALUES (?, ?, ?, ?, ?)", ROWS)
    return RecordingConnection(con)


def ids(rows):
    return [r["id"] for r in rows]


def test_the_original_is_really_vulnerable(db):
    # Shows why the exercise exists: the OR condition returns another merchant's payment.
    assert "pay_2001" in ids(find_payments_unsafe(db.con, "m_100", "x' OR '1'='1"))


def test_normal_queries_work(db):
    assert ids(find_payments(db, "m_100")) == ["pay_1001", "pay_1002", "pay_1003", "pay_1004"]
    assert ids(find_payments(db, "m_100", ["captured"])) == ["pay_1001"]
    assert ids(find_payments(db, "m_100", ["captured", "refunded"])) == ["pay_1001", "pay_1002"]
    assert set(find_payments(db, "m_200")[0]) == {"id", "merchant_id", "amount_minor", "currency", "status"}


def test_a_quote_in_a_legitimate_value_just_works(db):
    assert ids(find_payments(db, "m_100", ["o'brien-hold"])) == ["pay_1004"]


@pytest.mark.parametrize("attack", ATTACKS)
def test_attacks_match_nothing_and_change_nothing(db, attack):
    assert find_payments(db, "m_100", [attack]) == []
    assert find_payments(db, attack) == []
    assert db.con.execute("SELECT count(*) FROM payments").fetchone()[0] == len(ROWS)


@pytest.mark.parametrize("attack", ATTACKS)
def test_untrusted_values_never_enter_the_sql_text(db, attack):
    find_payments(db, attack, [attack, "captured"])
    assert db.calls, "find_payments must query through the connection it is given"
    for sql, params in db.calls:
        assert attack not in sql
        assert "captured" not in sql
    assert db.calls[-1][1].count(attack) == 2  # bound twice: merchant id and status


def test_one_placeholder_per_status(db):
    find_payments(db, "m_100", ["captured", "refunded", "failed"])
    sql, params = db.calls[-1]
    assert sql.count("?") == 4 and params == ("m_100", "captured", "refunded", "failed")


def test_empty_status_list_matches_nothing_without_a_query(db):
    assert find_payments(db, "m_100", []) == []
    assert db.calls == []


def test_sort_and_direction_come_from_allow_lists(db):
    assert ids(find_payments(db, "m_100", sort="amount")) == ["pay_1004", "pay_1002", "pay_1001", "pay_1003"]
    assert ids(find_payments(db, "m_100", sort="amount", direction="DESC"))[0] == "pay_1003"
    for bad_sort in ["amount_minor; DROP TABLE payments", "1", "(SELECT 1)", "merchant_id"]:
        with pytest.raises(ValueError):
            find_payments(db, "m_100", sort=bad_sort)
    for bad_dir in ["ASC; --", "up", ""]:
        with pytest.raises(ValueError):
            find_payments(db, "m_100", direction=bad_dir)
    assert db.con.execute("SELECT count(*) FROM payments").fetchone()[0] == len(ROWS)
