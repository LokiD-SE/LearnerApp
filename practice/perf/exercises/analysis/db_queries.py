"""Exercise: fewer queries per request (the N+1 problem).

``latest_payments_n_plus_one`` is finished and shows the problem: one query for the payments, then one more
query per payment to find the merchant's name. Your job is to send the same answer with far fewer queries.

The connection offers ``conn.execute(sql, params)`` only, and every call is one round trip to the database.
"""


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
    """TODO: the same rows as ``latest_payments_n_plus_one(conn, limit)`` - ``(payment id, merchant name,
    amount_cents)``, newest payment (highest id) first - using exactly ONE query (a JOIN)."""
    raise NotImplementedError("send one query")


def totals_for(conn, merchant_ids):
    """TODO: ``{merchant_id: (number of captured payments, their total amount_cents)}`` for every id in
    ``merchant_ids``, using ONE query for the whole list (``WHERE merchant_id IN (?, ?, ...)`` with ``GROUP BY``)
    and no query at all for an empty list.

    - Only payments whose status is 'captured' count.
    - A merchant with no captured payments still appears, as ``(0, 0)``.
    - Build the placeholders (one ``?`` per id) and pass the ids as parameters; never put an id into the SQL text.
    """
    raise NotImplementedError("send one query for all the ids")
