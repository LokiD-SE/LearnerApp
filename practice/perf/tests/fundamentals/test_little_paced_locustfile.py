from pathlib import Path

import pytest
from load_tools import practice_file, read_locust_stats, run_locust
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

LOCUSTFILE = practice_file("fundamentals/little_paced_locustfile.py")
TARGET = 20  # requests per second over 5 users
SECONDS = 3


def run(tmp_path: Path, latency_ms: float) -> dict[str, dict]:
    # Final totals from Locust's JSON: the _stats.csv file is rewritten once a second and can miss the end.
    with serve(TargetConfig(latency_ms=latency_ms, capacity=16)) as base:
        prefix = run_locust(LOCUSTFILE, base, users=5, spawn_rate=50, run_time=f"{SECONDS}s", out_dir=tmp_path)
    return read_locust_stats(prefix)


def achieved_rate(entry: dict, users: int = 5) -> float:
    """Requests per second over the time the requests actually ran (first to last), not the nominal run time:
    on a busy machine Locust's start-up can take a noticeable part of a 3-second run. Each user's first
    request opens the span, so ``users`` requests are fence posts, not intervals: (n - users) / span."""
    span = entry["last_request_timestamp"] - entry["start_time"]
    return (entry["num_requests"] - users) / span if span > 0 else 0.0


def test_paced_users_hit_the_target_rate_when_the_server_keeps_up(tmp_path):
    stats = run(tmp_path, latency_ms=20)
    assert "GET /v1/payments" in stats, f"no GET /v1/payments requests recorded: {sorted(stats)}"
    lists = stats["GET /v1/payments"]
    assert int(lists["num_failures"]) == 0, "requests failed - is the bearer token sent?"
    rate = achieved_rate(lists)
    # about 20 requests/s; a closed loop with no wait would send hundreds per second
    assert int(lists["num_requests"]) >= 20, lists["num_requests"]
    assert 0.6 * TARGET <= rate <= 1.3 * TARGET, rate
    assert int(stats["POST /auth/token"]["num_requests"]) == 5  # one token per user, from on_start


def test_pacing_cannot_beat_a_slow_server(tmp_path):
    # 500 ms per request: each user can manage at most 2 per second, so 5 users fall well short of 20/s
    stats = run(tmp_path, latency_ms=500)
    entry = stats["GET /v1/payments"]
    assert int(entry["num_requests"]) >= 5, entry["num_requests"]
    assert achieved_rate(entry) <= 0.6 * TARGET, achieved_rate(entry)
