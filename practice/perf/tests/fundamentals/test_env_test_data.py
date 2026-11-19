import pytest
from fundamentals.env_test_data import assign_credentials, create_payments, idempotency_key
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise


def test_credentials_are_unique_and_ordered():
    creds = assign_credentials(3)
    assert creds == [("merchant-1", "secret-1"), ("merchant-2", "secret-2"), ("merchant-3", "secret-3")]
    assert len(set(assign_credentials(50))) == 50


@pytest.mark.parametrize("users", [0, 51])
def test_credentials_refuse_impossible_counts(users):
    with pytest.raises(ValueError):
        assign_credentials(users)


def test_keys_are_unique_per_run_user_and_iteration():
    keys = {idempotency_key(run, u, i) for run in ("run-a", "run-b") for u in range(5) for i in range(10)}
    assert len(keys) == 100
    assert idempotency_key("run-7", 2, 3) == "run-7-u2-i3"


@pytest.mark.parametrize("args", [("", 0, 0), ("r", -1, 0), ("r", 0, -1), ("x" * 260, 0, 0)])
def test_keys_reject_bad_input(args):
    with pytest.raises(ValueError):
        idempotency_key(*args)


def test_unique_keys_create_every_payment():
    with serve(TargetConfig(latency_ms=0)) as base:
        result = create_payments(base, virtual_users=3, iterations=4, run_id="run-1")
    assert (result.created, result.replayed, result.distinct_ids) == (12, 0, 12)


def test_a_second_run_with_the_same_run_id_only_replays():
    # The server remembers keys: reusing the run id measures the replay cache, not payment creation.
    with serve(TargetConfig(latency_ms=0)) as base:
        first = create_payments(base, virtual_users=2, iterations=3, run_id="run-1")
        again = create_payments(base, virtual_users=2, iterations=3, run_id="run-1")
        fresh = create_payments(base, virtual_users=2, iterations=3, run_id="run-2")
    assert (first.created, first.replayed) == (6, 0)
    assert (again.created, again.replayed) == (0, 6)
    assert (fresh.created, fresh.replayed) == (6, 0)
