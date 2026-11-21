"""Reconciling what the load script thinks it did with what the payment API says it did (no imports needed).

A ledger is a list of records ``{"logical": id, "attempts": [{"key", "status", "replayed"}, ...], "outcome": ...}``
(the shape ``ppay_retry.submit_payment`` returns; ``status`` is ``None`` when no answer arrived). ``metrics`` is the
API's ``GET /metrics`` body; only ``payments_created`` and ``idempotent_replays`` are used here.

1. ``summarise(ledger)`` - ``{"logical", "attempts", "created", "replays", "failed", "timeouts", "unconfirmed"}``:
   ``logical`` records, ``attempts`` in total, ``created`` attempts answered 2xx that were NOT replays, ``replays``
   attempts answered 2xx with ``replayed`` true, ``failed`` attempts answered with a status that is not 2xx,
   ``timeouts`` attempts with ``status`` None, and ``unconfirmed`` logical payments that never got a 2xx.
2. ``created_bounds(ledger, in_flight=0)`` - ``(low, high)``: how many payments the API can have created given what
   the script saw. ``low`` is the number of ``created`` attempts (each is proof). ``high`` adds the timeouts (a
   request that timed out may still have been carried out) and ``in_flight``, the number of requests that were still
   running when the test was stopped and so never reached the ledger. (The API in these lessons returns 500 BEFORE it
   stores anything, so a 500 does not count towards ``high``.)
3. ``replay_share(metrics)`` - ``idempotent_replays / (payments_created + idempotent_replays)`` as a float, 0.0
   when both are zero. A big share means the run mostly measured replays, which cost almost nothing.
4. ``reconcile(ledger, metrics, in_flight=0)`` - ``{"bounds": (low, high), "server_created": n, "logical": number of records,
   "verdict": v}`` with ``v`` one of
   - ``"unexplained"``: the API's ``payments_created`` is below ``low`` or above ``high``;
   - ``"duplicates"``: within the bounds but larger than the number of logical payments plus ``in_flight``, so some
     payment exists twice;
   - ``"ok"`` otherwise.
   Check them in that order.
"""

from __future__ import annotations


def _attempts(ledger):
    return [a for record in ledger for a in record["attempts"]]


def summarise(ledger):
    attempts = _attempts(ledger)
    ok = [a for a in attempts if a["status"] is not None and 200 <= a["status"] < 300]
    unconfirmed = [
        r for r in ledger
        if not any(a["status"] is not None and 200 <= a["status"] < 300 for a in r["attempts"])
    ]
    return {
        "logical": len(ledger),
        "attempts": len(attempts),
        "created": sum(1 for a in ok if not a["replayed"]),
        "replays": sum(1 for a in ok if a["replayed"]),
        "failed": sum(1 for a in attempts if a["status"] is not None and not 200 <= a["status"] < 300),
        "timeouts": sum(1 for a in attempts if a["status"] is None),
        "unconfirmed": len(unconfirmed),
    }


def created_bounds(ledger, in_flight=0):
    s = summarise(ledger)
    return s["created"], s["created"] + s["timeouts"] + in_flight


def replay_share(metrics):
    created, replays = metrics["payments_created"], metrics["idempotent_replays"]
    total = created + replays
    return replays / total if total else 0.0


def reconcile(ledger, metrics, in_flight=0):
    low, high = created_bounds(ledger, in_flight)
    server = metrics["payments_created"]
    if server < low or server > high:
        verdict = "unexplained"
    elif server > len(ledger) + in_flight:
        verdict = "duplicates"
    else:
        verdict = "ok"
    return {"bounds": (low, high), "server_created": server, "logical": len(ledger), "verdict": verdict}
