import threading
import time
import urllib.request

import pytest
from fundamentals.little_check import littles_law_report, mean_residence, throughput, time_average_in_system
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

# Three requests over a 4-second window: [0,2], [1,3], [2.5,3.5]
SAMPLE = [(0.0, 2.0), (1.0, 3.0), (2.5, 3.5)]


def test_time_average_in_system():
    # area = 2 + 2 + 1 = 5 request-seconds over 4 s
    assert time_average_in_system(SAMPLE, 0.0, 4.0) == pytest.approx(1.25)


def test_time_average_clips_to_the_window():
    # inside [1, 3]: 1 + 2 + 0.5 = 3.5 request-seconds over 2 s
    assert time_average_in_system(SAMPLE, 1.0, 3.0) == pytest.approx(1.75)


def test_throughput_counts_completions_inside_the_window():
    assert throughput(SAMPLE, 0.0, 4.0) == pytest.approx(0.75)
    assert throughput(SAMPLE, 0.0, 3.0) == pytest.approx(2 / 3)


def test_mean_residence_uses_completed_requests():
    assert mean_residence(SAMPLE, 0.0, 4.0) == pytest.approx(5 / 3)
    with pytest.raises(ValueError):
        mean_residence(SAMPLE, 0.0, 1.0)


def test_rejects_bad_windows_and_intervals():
    with pytest.raises(ValueError):
        time_average_in_system(SAMPLE, 2.0, 2.0)
    with pytest.raises(ValueError):
        throughput([(3.0, 1.0)], 0.0, 4.0)


def test_report_is_exact_when_the_window_starts_and_ends_empty():
    report = littles_law_report(SAMPLE)
    assert report["L"] == pytest.approx(5 / 3.5)
    assert report["XR"] == pytest.approx(report["L"])
    assert report["relative_error"] == pytest.approx(0, abs=1e-12)


def test_report_shows_end_effects_inside_a_busy_window():
    report = littles_law_report(SAMPLE, 1.0, 3.0)
    # L = 1.75, X = 1 per s, R = 2 s -> X*R = 2: the cut requests make them differ
    assert report["L"] == pytest.approx(1.75)
    assert report["XR"] == pytest.approx(2.0)
    assert report["relative_error"] == pytest.approx(0.25 / 1.75)


def closed_loop_intervals(base, users=4, seconds=0.6):
    """A tiny closed-loop load generator: each user sends the next request when the previous reply arrives."""
    out, lock = [], threading.Lock()
    stop = time.perf_counter() + seconds
    body = b'{"client_id": "merchant-1", "client_secret": "secret-1"}'

    def user():
        while time.perf_counter() < stop:
            start = time.perf_counter()
            req = urllib.request.Request(base + "/auth/token", data=body, method="POST",
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5).read()
            with lock:
                out.append((start, time.perf_counter()))

    threads = [threading.Thread(target=user) for _ in range(users)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return out


def test_littles_law_holds_on_a_real_closed_loop_run():
    with serve(TargetConfig(latency_ms=20, capacity=16)) as base:
        intervals = closed_loop_intervals(base, users=4)
    report = littles_law_report(intervals)
    assert len(intervals) > 20
    assert report["relative_error"] < 1e-9
    # 4 users with no think time keep at most 4 requests in the system, and nearly always 4 on average
    assert 3.0 < report["L"] <= 4.0 + 1e-9
