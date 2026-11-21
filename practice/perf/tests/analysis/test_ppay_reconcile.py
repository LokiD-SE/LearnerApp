"""Checks exercises/analysis/ppay_reconcile.py: client ledger against the API's own counters.

Hand-made ledgers first, then the lesson's experiment against the practice API: the first request times out on the
client while the API carries it out, and the script retries at once or after the API has finished (about a second per
scenario because the API needs 200 ms for a payment and the counters are read after it has finished)."""

import pytest
from ppay_fixture import load_exercise, timeout_scenario

pytestmark = pytest.mark.exercise

rc = load_exercise("analysis/ppay_reconcile.py")


def rec(logical, *attempts):
    """attempts are (status, replayed) pairs; the key is not used by the reconciliation."""
    return {"logical": logical, "outcome": "?",
            "attempts": [{"key": f"k-{logical}", "status": s, "replayed": r} for s, r in attempts]}


LEDGER = [
    rec("a", (201, False)),
    rec("b", (500, False), (201, False)),
    rec("c", (None, False), (201, True)),
    rec("d", (503, False), (503, False), (503, False), (503, False)),
    rec("e", (None, False), (None, False)),
]


def test_summarise_counts_every_kind_of_attempt():
    assert rc.summarise(LEDGER) == {"logical": 5, "attempts": 11, "created": 2, "replays": 1, "failed": 5,
                                    "timeouts": 3, "unconfirmed": 2}


def test_summarise_of_nothing_is_all_zeros():
    assert rc.summarise([]) == {"logical": 0, "attempts": 0, "created": 0, "replays": 0, "failed": 0,
                                "timeouts": 0, "unconfirmed": 0}


def test_bounds_are_proven_creations_up_to_proven_plus_timeouts():
    assert rc.created_bounds(LEDGER) == (2, 5)  # 500 and 503 do not count: nothing was stored
    assert rc.created_bounds(LEDGER, in_flight=4) == (2, 9)
    assert rc.created_bounds([]) == (0, 0)


def test_replay_share_is_the_replays_over_everything_that_succeeded():
    assert rc.replay_share({"payments_created": 20, "idempotent_replays": 3272}) == pytest.approx(3272 / 3292)
    assert rc.replay_share({"payments_created": 10, "idempotent_replays": 0}) == 0.0
    assert rc.replay_share({"payments_created": 0, "idempotent_replays": 0}) == 0.0


def test_a_server_count_inside_the_bounds_and_not_above_the_logical_count_is_ok():
    got = rc.reconcile(LEDGER, {"payments_created": 3, "idempotent_replays": 1})
    assert got == {"bounds": (2, 5), "server_created": 3, "logical": 5, "verdict": "ok"}
    assert rc.reconcile(LEDGER, {"payments_created": 2})["verdict"] == "ok"  # low edge
    assert rc.reconcile(LEDGER, {"payments_created": 5})["verdict"] == "ok"  # high edge, equal to the logical count


def test_outside_the_bounds_is_unexplained_and_checked_before_duplicates():
    assert rc.reconcile(LEDGER, {"payments_created": 1})["verdict"] == "unexplained"
    assert rc.reconcile(LEDGER, {"payments_created": 6})["verdict"] == "unexplained"


def test_more_payments_than_logical_payments_is_a_duplicate():
    ledger = [rec("a", (None, False), (201, False)), rec("b", (201, False))]
    got = rc.reconcile(ledger, {"payments_created": 3})
    assert got["bounds"] == (2, 3) and got["verdict"] == "duplicates"
    assert rc.reconcile(ledger, {"payments_created": 2})["verdict"] == "ok"


def test_requests_still_running_when_the_test_stopped_are_allowed_for():
    ledger = [rec("a", (201, False)), rec("b", (201, False))]
    assert rc.reconcile(ledger, {"payments_created": 4})["verdict"] == "unexplained"
    assert rc.reconcile(ledger, {"payments_created": 4}, in_flight=2)["verdict"] == "ok"
    assert rc.reconcile(ledger, {"payments_created": 1}, in_flight=2)["verdict"] == "unexplained"


def test_an_empty_ledger_with_no_payments_is_ok():
    assert rc.reconcile([], {"payments_created": 0})["verdict"] == "ok"


@pytest.mark.parametrize("wait_s, same_key, verdict, created, replays", [
    (0.0, True, "duplicates", 2, 0),   # the key is not stored until the first request finishes
    (0.3, True, "ok", 1, 1),           # the API had finished: the retry is a replay
    (0.0, False, "duplicates", 2, 0),  # a new key is a new payment
    (0.3, False, "duplicates", 2, 0),
])
def test_the_timeout_retry_experiment_against_the_api(wait_s, same_key, verdict, created, replays):
    ledger, m = timeout_scenario(wait_s, same_key)
    assert (m["payments_created"], m["idempotent_replays"]) == (created, replays)
    assert rc.reconcile(ledger, m)["verdict"] == verdict
