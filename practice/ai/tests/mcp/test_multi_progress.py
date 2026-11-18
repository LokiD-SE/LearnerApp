import pytest
from mcp.multi_progress import ProgressTracker, cancellation_for, timed_out

pytestmark = pytest.mark.exercise


def test_tokens_are_unique_across_servers_and_requests():
    t = ProgressTracker()
    tokens = [t.new_token("ledger", 1), t.new_token("support", 1), t.new_token("ledger", 2)]
    assert len(set(tokens)) == 3
    assert tokens[0].startswith("ledger-") and tokens[1].startswith("support-")


def test_accepts_increasing_progress_and_reports_overall():
    t = ProgressTracker()
    a = t.new_token("ledger", 1)
    b = t.new_token("support", 7)
    assert t.on_notification("ledger", {"progressToken": a, "progress": 20, "total": 100, "message": "page 1"})
    assert t.on_notification("support", {"progressToken": b, "progress": 3, "total": 4})
    assert t.overall() == (0.475, 0)
    assert t.ops[a].message == "page 1"


def test_progress_without_total_counts_as_unknown():
    t = ProgressTracker()
    a = t.new_token("ledger", 1)
    b = t.new_token("kb", 2)
    t.on_notification("ledger", {"progressToken": a, "progress": 1, "total": 2})
    t.on_notification("kb", {"progressToken": b, "progress": 40})
    assert t.overall() == (0.5, 1)
    assert ProgressTracker().overall() == (None, 0)


def test_non_increasing_progress_is_ignored():
    t = ProgressTracker()
    a = t.new_token("ledger", 1)
    assert t.on_notification("ledger", {"progressToken": a, "progress": 5, "total": 10})
    assert not t.on_notification("ledger", {"progressToken": a, "progress": 5, "total": 10})
    assert not t.on_notification("ledger", {"progressToken": a, "progress": 4, "total": 10})
    assert t.ops[a].progress == 5
    assert len(t.ignored) == 2


def test_unknown_foreign_and_completed_tokens_are_ignored():
    t = ProgressTracker()
    a = t.new_token("ledger", 1)
    assert not t.on_notification("ledger", {"progressToken": "nope", "progress": 1})
    assert not t.on_notification("support", {"progressToken": a, "progress": 1})
    t.complete(a)
    assert not t.on_notification("ledger", {"progressToken": a, "progress": 2})
    assert not t.on_notification("ledger", {"progressToken": t.new_token("ledger", 2)})
    assert len(t.ignored) == 4
    assert any("belongs to ledger" in r for r in t.ignored)


def test_completed_operations_leave_the_overall_figure():
    t = ProgressTracker()
    a = t.new_token("ledger", 1)
    b = t.new_token("support", 2)
    t.on_notification("ledger", {"progressToken": a, "progress": 10, "total": 10})
    t.on_notification("support", {"progressToken": b, "progress": 1, "total": 4})
    t.complete(a)
    assert t.overall() == (0.25, 0)


def test_stdio_cancellation_is_a_notification_message():
    msg = cancellation_for("stdio", 42, "user pressed stop")
    assert msg == {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 42, "reason": "user pressed stop"}}
    assert "id" not in msg


def test_http_cancellation_closes_the_stream_and_sends_nothing():
    assert cancellation_for("http", "r-9", "timeout") == {"action": "close_stream", "requestId": "r-9"}
    with pytest.raises(ValueError):
        cancellation_for("pigeon", 1, "x")


@pytest.mark.parametrize(
    "started,last,now,expected",
    [
        (0, None, 5, None),
        (0, None, 10, "idle"),
        (0, 25, 30, None),
        (0, 25, 35, "idle"),
        (0, 58, 60, "max"),
        (0, None, 61, "max"),
    ],
)
def test_timed_out_resets_on_progress_but_enforces_a_maximum(started, last, now, expected):
    assert timed_out(started, last, now, idle=10, maximum=60) == expected
