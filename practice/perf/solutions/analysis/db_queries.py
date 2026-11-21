"""Solution: fewer queries per request (the N+1 problem)."""


def latest_payments_n_plus_one(conn, limit):
    """Given: 1 + ``limit`` queries."""
    payments = conn.execute(
        "SELECT id, merchant_id, amount_cents FROM payments ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    rows = []
    for payment_id, merchant_id, amount in payments:
        name = conn.execute("SELECT name FROM merchants WHERE id = ?", (merchant_id,)).fetchone()[0]
        rows.append((payment_id, name, amount))
    return rows


def latest_payments(conn, limit):
    """One query: the JOIN lets the database find each merchant, instead of the application asking N times."""
    return conn.execute(
        "SELECT p.id, m.name, p.amount_cents FROM payments p JOIN merchants m ON m.id = p.merchant_id "
        "ORDER BY p.id DESC LIMIT ?",
        (limit,),
    ).fetchall()


def totals_for(conn, merchant_ids):
    """One query for the whole list; one placeholder per id; ids that have no captured payments get (0, 0)."""
    ids = list(merchant_ids)
    if not ids:
        return {}
    placeholders = ", ".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT merchant_id, count(*), sum(amount_cents) FROM payments "
        f"WHERE status = 'captured' AND merchant_id IN ({placeholders}) GROUP BY merchant_id",
        ids,
    ).fetchall()
    found = {merchant_id: (count, total) for merchant_id, count, total in rows}
    return {merchant_id: found.get(merchant_id, (0, 0)) for merchant_id in ids}
