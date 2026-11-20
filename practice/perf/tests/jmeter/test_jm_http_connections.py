"""Checks exercises/jmeter/jm_http_connections.py on hand-made logs, then on real JMeter runs against a server
that records which TCP connection carried each request (support/jm_http_fixture.py)."""

from pathlib import Path

import pytest
from jm_http_fixture import Hit, serve_recording
from jmeter.jm_http_connections import connection_header_values, requests_per_connection, reuse_pattern
from load_tools import jmeter_home, read_jtl, run_jmeter

pytestmark = pytest.mark.exercise

PLAN = Path(__file__).parent / "fixtures" / "jm_http_conn.jmx"
THREADS, LOOPS, PER_ITERATION = 2, 3, 3  # the plan sends three requests per iteration


def hits(*connections, header="keep-alive"):
    return [Hit(c, "GET", "/conn", {"Connection": header} if header else {}) for c in connections]


def test_counts_and_header_values():
    log = hits("a", "a", "b") + hits("c", header=None) + [Hit("c", "GET", "/conn", {"connection": "Close"})]
    assert requests_per_connection(log) == {"a": 2, "b": 1, "c": 2}
    assert connection_header_values(log) == {"keep-alive": 3, "(none)": 1, "close": 1}


def test_patterns_on_hand_made_logs():
    assert reuse_pattern(hits("a", "b", "c", "d"), threads=2, loops=1) == "per-request"
    assert reuse_pattern(hits("a", "a", "b", "b", "c", "c", "d", "d"), threads=2, loops=2) == "per-iteration"
    assert reuse_pattern(hits("a", "a", "a", "b", "b", "b"), threads=2, loops=3) == "per-thread"
    assert reuse_pattern(hits("a", "a", "b", "c", "c", "c"), threads=2, loops=1) == "mixed"
    assert reuse_pattern(hits("a"), threads=1, loops=1) == "per-request"  # the first matching pattern wins
    with pytest.raises(ValueError):
        reuse_pattern([], threads=1, loops=1)


def run(tmp_path, keepalive, same_user, **props):
    plan = tmp_path / "conn.jmx"
    plan.write_text(PLAN.read_text().replace("KEEPALIVE", keepalive).replace("SAMEUSER", same_user))
    with serve_recording() as (base, log):
        rows = read_jtl(run_jmeter(plan, {"port": base.rsplit(":", 1)[1], "threads": THREADS, "loops": LOOPS,
                                          **props}, tmp_path / "out"))
    assert len(rows) == len(log) == THREADS * LOOPS * PER_ITERATION and all(r["success"] == "true" for r in rows)
    return log


jmeter = pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")


@jmeter
def test_real_runs_show_each_reuse_pattern(tmp_path):
    on = run(tmp_path, "true", "true")
    assert reuse_pattern(on, THREADS, LOOPS) == "per-thread"
    assert connection_header_values(on) == {"keep-alive": len(on)}

    off = run(tmp_path, "false", "true")
    assert reuse_pattern(off, THREADS, LOOPS) == "per-request"
    assert connection_header_values(off) == {"close": len(off)}

    new_user = run(tmp_path, "true", "false")  # "Same user on each iteration" off: a new user, a new connection
    assert reuse_pattern(new_user, THREADS, LOOPS) == "per-iteration"
    assert sorted(requests_per_connection(new_user).values()) == [PER_ITERATION] * (THREADS * LOOPS)

    kept = run(tmp_path, "true", "false", **{"httpclient.reset_state_on_thread_group_iteration": "false"})
    assert reuse_pattern(kept, THREADS, LOOPS) == "per-thread"
