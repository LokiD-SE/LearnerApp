"""Checks exercises/analysis/ppay_retry.py: one key per logical payment, reused by every retry.

Hand-made sends first (no network), then the same code against the practice API with injected 500s, then one real
Locust run (about 5 s) whose users use the module through support/ppay_user_locustfile.py."""

import tempfile
import uuid
from pathlib import Path

import pytest
from ppay_fixture import load_exercise, make_send, metrics, run_pay_locust, token
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

rt = load_exercise("analysis/ppay_retry.py")


def test_a_new_key_is_a_random_version_4_uuid_string():
    a, b = rt.new_key(), rt.new_key()
    assert isinstance(a, str) and a != b
    assert uuid.UUID(a).version == 4


@pytest.mark.parametrize("status", [200, 201, 204])
def test_a_success_is_never_retried(status):
    assert rt.retry_wait(status, {}, 1) is None


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422])
def test_a_client_error_is_never_retried(status):
    assert rt.retry_wait(status, {}, 1) is None


@pytest.mark.parametrize("status", [None, 429, 500, 502, 503, 504])
def test_no_answer_429_and_5xx_are_retried(status):
    assert rt.retry_wait(status, {}, 1) == pytest.approx(0.05)


def test_the_back_off_doubles_and_is_capped(monkeypatch):
    assert [rt.retry_wait(500, {}, n) for n in (1, 2, 3, 4)] == pytest.approx([0.05, 0.1, 0.1, 0.1])
    monkeypatch.setattr(rt, "MAX_WAIT_S", 10)
    assert [rt.retry_wait(500, {}, n) for n in (1, 2, 3, 4)] == pytest.approx([0.05, 0.1, 0.2, 0.4])


def test_retry_after_in_whole_seconds_wins_over_the_back_off_but_not_over_the_cap(monkeypatch):
    assert rt.retry_wait(503, {"Retry-After": "1"}, 1) == pytest.approx(0.1)  # 1 s, capped
    assert rt.retry_wait(429, {"retry-after": "0"}, 3) == 0.0  # the server said "now"
    monkeypatch.setattr(rt, "MAX_WAIT_S", 10)
    assert rt.retry_wait(503, {"RETRY-AFTER": "2"}, 1) == pytest.approx(2.0)


def test_a_retry_after_that_is_not_a_number_of_seconds_is_ignored():
    date = {"Retry-After": "Fri, 31 Dec 2027 23:59:59 GMT"}
    assert rt.retry_wait(503, date, 2) == pytest.approx(0.1)  # back-off for attempt 2


def scripted(*answers):
    calls, sleeps = [], []

    def send(key):
        calls.append(key)
        answer = answers[len(calls) - 1]
        if isinstance(answer, Exception):
            raise answer
        return answer

    return send, calls, sleeps


def test_a_first_try_success_makes_one_attempt_and_no_wait():
    send, calls, sleeps = scripted((201, {}))
    rec = rt.submit_payment(send, "pay-1", sleep=sleeps.append)
    assert rec["logical"] == "pay-1" and rec["outcome"] == "ok" and sleeps == []
    assert rec["attempts"] == [{"key": calls[0], "status": 201, "replayed": False}]


def test_every_retry_carries_the_same_key_and_waits_between_attempts():
    send, calls, sleeps = scripted((500, {}), (503, {"Retry-After": "1"}), (201, {}))
    rec = rt.submit_payment(send, "pay-2", sleep=sleeps.append)
    assert rec["outcome"] == "ok" and [a["status"] for a in rec["attempts"]] == [500, 503, 201]
    assert len(set(calls)) == 1 and {a["key"] for a in rec["attempts"]} == {calls[0]}
    assert sleeps == pytest.approx([0.05, 0.1])


def test_a_timeout_is_an_attempt_with_no_status_and_is_retried_with_the_same_key():
    send, calls, sleeps = scripted(TimeoutError("slow"), (201, {"Idempotent-Replayed": "true"}))
    rec = rt.submit_payment(send, "pay-3", sleep=sleeps.append)
    assert [a["status"] for a in rec["attempts"]] == [None, 201]
    assert [a["replayed"] for a in rec["attempts"]] == [False, True]
    assert len(set(calls)) == 1 and rec["outcome"] == "ok"


def test_a_bad_request_is_rejected_at_once_without_waiting():
    send, calls, sleeps = scripted((422, {}))
    rec = rt.submit_payment(send, "pay-4", sleep=sleeps.append)
    assert rec["outcome"] == "rejected" and len(rec["attempts"]) == 1 and sleeps == []


def test_a_payment_that_never_works_gives_up_after_max_attempts_and_does_not_wait_after_the_last():
    send, calls, sleeps = scripted(*[(503, {})] * 6)
    rec = rt.submit_payment(send, "pay-5", sleep=sleeps.append)
    assert rec["outcome"] == "gave-up" and len(rec["attempts"]) == 4 and len(sleeps) == 3
    send, calls, sleeps = scripted(*[(500, {})] * 6)
    rec = rt.submit_payment(send, "pay-6", sleep=sleeps.append, max_attempts=2)
    assert len(rec["attempts"]) == 2 and len(sleeps) == 1


def test_two_logical_payments_never_share_a_key():
    send, calls, sleeps = scripted((201, {}), (201, {}))
    a = rt.submit_payment(send, "a", sleep=sleeps.append)
    b = rt.submit_payment(send, "b", sleep=sleeps.append)
    assert a["attempts"][0]["key"] != b["attempts"][0]["key"]


def test_against_the_api_with_injected_500s_a_retry_creates_exactly_one_payment():
    with serve(TargetConfig(latency_ms=1, error_rate=0.5)) as url:
        send = make_send(url, token(url))
        records = [rt.submit_payment(send, f"pay-{i}", sleep=lambda s: None) for i in range(40)]
        m = metrics(url)
    ok = [r for r in records if r["outcome"] == "ok"]
    assert any(len(r["attempts"]) > 1 for r in records)
    assert all(len({a["key"] for a in r["attempts"]}) == 1 for r in records)
    assert m["payments_created"] == len(ok) and m["idempotent_replays"] == 0


def test_in_a_real_locust_run_retries_keep_their_key_and_create_no_duplicates():
    config = TargetConfig(latency_ms=20, capacity=2, queue_limit=2, error_rate=0.2)
    with serve(config) as url, tempfile.TemporaryDirectory() as out:
        ledger, stats = run_pay_locust(url, Path(out), users=6, run_time="4s")
        m = metrics(url)
    assert len(ledger) >= 20 and stats["POST /v1/payments"]["num_requests"] >= len(ledger)
    assert all(len({a["key"] for a in r["attempts"]}) == 1 and len(r["attempts"]) <= 4 for r in ledger)
    for r in ledger:
        codes = [a["status"] for a in r["attempts"]]
        assert not any(c is not None and 200 <= c < 300 for c in codes[:-1]), "retried after a success"
    assert any(len(r["attempts"]) > 1 for r in ledger)
    ok = sum(1 for r in ledger if r["outcome"] == "ok")
    # a user stopped mid-request created a payment the ledger never saw: at most one per user
    assert ok <= m["payments_created"] <= ok + 6 and m["idempotent_replays"] == 0
