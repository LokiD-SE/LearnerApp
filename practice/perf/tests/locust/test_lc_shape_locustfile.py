"""Runs exercises/locust/lc_shape_locustfile.py with real Locust (headless, in a subprocess) against the practice
API and reads the run's history: a shape must walk 1 -> 3 -> 5 users and stop by itself.

``run_locust`` passes -u, -r and -t, which Locust ignores (with a warning) when a shape class is present - that is
part of what the lesson teaches. A shape that never returns None would run forever, so the run has a timeout."""

import subprocess
import time

import pytest
from lc_shape_fixture import read_history
from load_tools import practice_file, read_locust_stats, run_locust
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("shape")
    started = time.time()
    with serve(TargetConfig(latency_ms=5)) as base:
        try:
            prefix = run_locust(practice_file("locust/lc_shape_locustfile.py"), base, 1, 1, "60s", out, timeout=45)
        except subprocess.TimeoutExpired:
            pytest.fail("the run never ended - tick() must return None after the last stage")
        except RuntimeError as exc:  # Locust failed to start
            pytest.fail(str(exc)[-1500:])
    return {"prefix": prefix, "seconds": time.time() - started}


def test_the_shape_ends_the_test_by_itself(run):
    # 9 s of stages plus start-up; -t was 60 s, so only the shape can have stopped it
    assert run["seconds"] < 25


def test_user_count_climbs_one_three_five(run):
    rows = read_history(f"{run['prefix']}_stats_history.csv")
    counts = [int(r["User Count"]) for r in rows]
    assert counts == sorted(counts), f"the user count went down: {counts}"
    assert max(counts) == 5, f"peak was {max(counts)}: {counts}"
    assert {1, 3, 5} <= set(counts), f"a step was never seen: {counts}"
    assert set(counts) <= {0, 1, 3, 5}, f"unexpected user counts: {counts}"


def test_every_user_logged_in_once_and_nothing_failed(run):
    stats = read_locust_stats(run["prefix"])
    assert stats["/auth/token"]["num_requests"] == 5  # five users were started in total, none restarted
    assert stats["/v1/payments"]["num_requests"] > 10
    assert all(s["num_failures"] == 0 for s in stats.values())
