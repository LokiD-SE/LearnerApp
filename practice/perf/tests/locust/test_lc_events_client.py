"""Checks exercises/locust/lc_events_client.py (calling the client directly with a stand-in for Locust's request
event) and exercises/locust/lc_events_ledger_locustfile.py (real Locust against the TCP ledger fixture)."""

import socket
import threading

import pytest
from lc_events_fixture import load_exercise, serve
from load_tools import practice_file, read_locust_stats, run_locust

pytestmark = pytest.mark.exercise

client_module = load_exercise("locust/lc_events_client.py")


class RecordingEvent:
    def __init__(self):
        self.fired = []

    def fire(self, **kwargs):
        self.fired.append(kwargs)


@pytest.fixture
def ledger():
    with serve() as running:
        yield running


def test_a_successful_call_returns_the_reply_and_fires_one_event(ledger):
    event = RecordingEvent()
    client = client_module.LedgerClient(ledger.host, event)
    assert client.balance("merchant-1") == "OK 125000"
    client.close()
    (fired,) = event.fired
    assert fired["request_type"] == "LEDGER" and fired["name"] == "BALANCE"
    assert fired["exception"] is None and fired["response"] == "OK 125000"
    assert fired["response_length"] == len("OK 125000")
    assert fired["response_time"] > 0 and fired["start_time"] > 1e9


def test_the_name_never_contains_the_arguments(ledger):
    event = RecordingEvent()
    client = client_module.LedgerClient(ledger.host, event)
    client.balance("merchant-17")
    client.transfer("merchant-17", "merchant-18", 99)
    client.close()
    assert [f["name"] for f in event.fired] == ["BALANCE", "TRANSFER"]


def test_response_time_is_in_milliseconds(ledger):
    event = RecordingEvent()
    client = client_module.LedgerClient(ledger.host, event)
    for _ in range(4):  # the 4th transfer takes 120 ms on the server
        client.transfer("merchant-1", "merchant-2", 1)
    client.close()
    times = [f["response_time"] for f in event.fired]
    assert times[3] >= 100, f"the slow transfer should take about 120 ms, got {times[3]}"
    assert times[3] < 5000, "seconds, not milliseconds?"


def test_an_err_reply_is_a_failed_request_with_the_reason(ledger):
    event = RecordingEvent()
    client = client_module.LedgerClient(ledger.host, event)
    results = [client.transfer("merchant-1", "merchant-2", 1250) for _ in range(5)]  # the 5th is declined
    client.close()
    assert [r is None for r in results] == [False, False, False, False, True]
    assert [f["exception"] is None for f in event.fired] == [True, True, True, True, False]
    error = event.fired[4]["exception"]
    assert isinstance(error, client_module.LedgerError) and str(error) == "insufficient_funds"
    assert event.fired[4]["response"] == "ERR insufficient_funds"


def test_a_server_that_hangs_up_is_a_failed_request_not_a_crash():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)

    def hang_up():
        conn, _ = server.accept()
        conn.recv(100)
        conn.close()

    threading.Thread(target=hang_up, daemon=True).start()
    event = RecordingEvent()
    client = client_module.LedgerClient(f"127.0.0.1:{server.getsockname()[1]}", event)
    assert client.balance("merchant-1") is None
    client.close()
    server.close()
    (fired,) = event.fired
    assert isinstance(fired["exception"], OSError)
    assert fired["response_length"] == 0


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("lc-events-client")
    with serve() as running:
        prefix = run_locust(practice_file("locust/lc_events_ledger_locustfile.py"), running.host, users=4,
                            spawn_rate=4, run_time="3s", out_dir=out)
        counts = dict(running.counts)
    return read_locust_stats(prefix), counts


def test_locust_records_the_ledger_calls_under_two_names(run):
    stats, _ = run
    assert set(stats) == {"BALANCE", "TRANSFER"}
    assert {e["method"] for e in stats.values()} == {"LEDGER"}
    assert stats["BALANCE"]["num_requests"] >= 30 and stats["TRANSFER"]["num_requests"] >= 10


def test_the_task_weights_are_three_to_one(run):
    stats, _ = run
    ratio = stats["BALANCE"]["num_requests"] / stats["TRANSFER"]["num_requests"]
    assert 1.5 < ratio < 6, f"BALANCE : TRANSFER = {ratio:.1f}, expected about 3"


def test_declined_transfers_are_failures_and_nothing_else_is(run):
    stats, counts = run
    assert stats["BALANCE"]["num_failures"] == 0
    # a call still in flight when the run stops is counted by the ledger but not by Locust: one per user at most
    assert counts["declined"] - 4 <= stats["TRANSFER"]["num_failures"] <= counts["declined"]


def test_each_user_opens_one_connection(run):
    _, counts = run
    assert counts["connections"] == 4
