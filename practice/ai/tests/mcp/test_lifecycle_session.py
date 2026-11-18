import pytest
from mcp.lifecycle_session import LegacyClientSession, LifecycleError, PendingRequests, required_capability

pytestmark = pytest.mark.exercise

INFO = {"name": "sandpay-desk", "version": "0.4.0"}


def session():
    return LegacyClientSession(["2025-06-18", "2025-11-25"], {"elicitation": {}}, INFO)


def init_ok(version="2025-11-25", capabilities=None):
    caps = {"tools": {"listChanged": True}} if capabilities is None else capabilities
    return {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": version, "capabilities": caps, "serverInfo": {"name": "lookup", "version": "1.2.0"}}}


def ready_session():
    s = session()
    s.start()
    s.on_initialize_response(init_ok())
    return s


def test_start_sends_initialize_with_the_latest_version():
    s = session()
    msg = s.start()
    assert msg == {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-11-25", "capabilities": {"elicitation": {}}, "clientInfo": INFO},
    }
    assert s.state == "initializing"


def test_start_only_once():
    s = session()
    s.start()
    with pytest.raises(LifecycleError):
        s.start()


def test_nothing_before_initialize():
    with pytest.raises(LifecycleError, match="new"):
        session().request("ping")


def test_only_ping_while_initializing():
    s = session()
    s.start()
    assert s.request("ping") == {"jsonrpc": "2.0", "id": 2, "method": "ping"}
    with pytest.raises(LifecycleError, match="ping"):
        s.request("tools/list")


def test_successful_response_returns_initialized_notification():
    s = session()
    s.start()
    note = s.on_initialize_response(init_ok())
    assert note == {"jsonrpc": "2.0", "method": "notifications/initialized"}
    assert s.state == "ready"
    assert s.protocol_version == "2025-11-25"
    assert s.server_capabilities == {"tools": {"listChanged": True}}


def test_unsupported_answer_closes_the_session():
    s = session()
    s.start()
    assert s.on_initialize_response(init_ok(version="2024-11-05")) is None
    assert s.state == "closed"


def test_error_answer_closes_the_session():
    s = session()
    s.start()
    reply = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "Unsupported protocol version"}}
    assert s.on_initialize_response(reply) is None
    assert s.state == "closed"


def test_response_without_outstanding_initialize_is_an_error():
    with pytest.raises(LifecycleError):
        session().on_initialize_response(init_ok())


def test_ready_session_numbers_requests_and_keeps_params():
    s = ready_session()
    assert s.request("tools/list") == {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    msg = s.request("tools/call", {"name": "find_merchant", "arguments": {"query": "m-204"}})
    assert msg["id"] == 3
    assert msg["params"]["name"] == "find_merchant"


def test_only_negotiated_capabilities_are_used():
    s = ready_session()
    with pytest.raises(LifecycleError, match="resources"):
        s.request("resources/read", {"uri": "sandpay://merchants/m-204"})
    assert s.request("ping")["method"] == "ping"


def test_initialize_twice_and_after_close():
    s = ready_session()
    with pytest.raises(LifecycleError):
        s.request("initialize")
    s.close()
    with pytest.raises(LifecycleError, match="closed"):
        s.request("ping")


@pytest.mark.parametrize(
    "method, capability",
    [("tools/call", "tools"), ("resources/list", "resources"), ("prompts/get", "prompts"), ("logging/setLevel", "logging"), ("completion/complete", "completions"), ("ping", None)],
)
def test_required_capability(method, capability):
    assert required_capability(method) == capability


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def test_pending_rejects_reusing_an_in_flight_id():
    p = PendingRequests(10, 60, Clock())
    p.track(5)
    with pytest.raises(ValueError):
        p.track(5)


def test_response_is_delivered_once_and_id_can_be_reused():
    p = PendingRequests(10, 60, Clock())
    p.track(5)
    assert p.on_response({"jsonrpc": "2.0", "id": 5, "result": {}}) == "deliver"
    assert p.on_response({"jsonrpc": "2.0", "id": 5, "result": {}}) == "ignore"
    p.track(5)
    assert p.in_flight() == [5]


def test_timeout_sends_cancelled_and_late_response_is_ignored():
    clock = Clock()
    p = PendingRequests(10, 60, clock)
    p.track(5)
    p.track(6)
    clock.now = 109.9
    assert p.expire() == []
    clock.now = 110.0
    assert p.expire() == [
        {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 5, "reason": "timeout after 10s"}},
        {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 6, "reason": "timeout after 10s"}},
    ]
    assert p.in_flight() == []
    assert p.on_response({"jsonrpc": "2.0", "id": 5, "result": {}}) == "ignore"


def test_progress_resets_the_clock_up_to_the_maximum():
    clock = Clock()
    p = PendingRequests(10, 25, clock)
    p.track("r1")
    clock.now = 108
    p.on_progress("r1")  # deadline 118
    clock.now = 117
    assert p.expire() == []
    p.on_progress("r1")  # 127 capped at 125
    clock.now = 124.9
    assert p.expire() == []
    clock.now = 125
    notes = p.expire()
    assert notes[0]["params"] == {"requestId": "r1", "reason": "timeout after 25s"}


def test_cancel_only_in_flight_requests():
    p = PendingRequests(10, 60, Clock())
    p.track(1)
    assert p.cancel(1, "user pressed Stop") == {
        "jsonrpc": "2.0",
        "method": "notifications/cancelled",
        "params": {"requestId": 1, "reason": "user pressed Stop"},
    }
    assert p.cancel(1, "again") is None
    assert p.cancel(99, "never sent") is None
    assert p.cancelled == {1}


def test_bad_timeouts_are_rejected():
    with pytest.raises(ValueError):
        PendingRequests(30, 10, Clock())
