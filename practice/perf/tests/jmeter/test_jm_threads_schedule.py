"""Exercise: ramp-up schedule (jmeter/jm_threads_schedule.py). One test runs real JMeter against the practice API."""

from pathlib import Path

import pytest
from jmeter.jm_threads_schedule import check_ramp, observed_offsets, start_offsets, thread_number
from load_tools import jmeter_home, read_jtl, run_jmeter
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

FIXTURES = Path(__file__).parent / "fixtures"


def rows(*samples):
    """JTL-like rows from (threadName, timeStamp) pairs."""
    return [{"threadName": name, "timeStamp": str(ts)} for name, ts in samples]


def test_manual_examples():
    # Component Reference: 10 threads, 100 s ramp-up -> 10 s apart, the tenth after 90 s, not 100 s
    assert start_offsets(10, 100) == [float(i * 10) for i in range(10)]
    # User manual 3.1: 30 threads over 120 s -> each successive thread 4 s later
    assert start_offsets(30, 120)[:3] == [0.0, 4.0, 8.0]


def test_one_thread_and_zero_ramp_start_at_once():
    assert start_offsets(1, 60) == [0.0]
    assert start_offsets(4, 0) == [0.0, 0.0, 0.0, 0.0]


def test_rejects_impossible_settings():
    with pytest.raises(ValueError):
        start_offsets(0, 10)
    with pytest.raises(ValueError):
        start_offsets(5, -1)


def test_thread_number_from_jtl_names():
    assert thread_number("Merchants 1-3") == 3
    assert thread_number("Checkout users 2-12") == 12
    with pytest.raises(ValueError):
        thread_number("Merchants")


def test_observed_offsets_use_each_threads_first_sample():
    data = rows(("G 1-2", 1_400), ("G 1-1", 1_000), ("G 1-1", 1_050), ("G 1-2", 1_900), ("G 1-3", 1_800))
    assert observed_offsets(data) == {1: 0, 2: 400, 3: 800}


def test_group_filter_ignores_a_setup_thread_group():
    data = rows(("Warm-up 1-1", 500), ("G 1-1", 1_000), ("G 1-2", 1_400))
    # unfiltered, the warm-up's "thread 1" (500) is taken as G's thread 1 and the origin moves 500 ms early
    assert observed_offsets(data) == {1: 0, 2: 900}
    assert observed_offsets(data, group="G") == {1: 0, 2: 400}


def test_check_ramp_reports_late_and_missing_threads():
    good = rows(("G 1-1", 0), ("G 1-2", 500), ("G 1-3", 1_010))
    assert check_ramp(good, threads=3, ramp_up_s=1.5) == []
    late = rows(("G 1-1", 0), ("G 1-2", 500), ("G 1-3", 1_400))
    problems = check_ramp(late, threads=3, ramp_up_s=1.5)
    assert len(problems) == 1 and "thread 3" in problems[0]
    missing = rows(("G 1-1", 0), ("G 1-2", 500))
    assert any("1..3" in p for p in check_ramp(missing, threads=3, ramp_up_s=1.5))


@pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")
def test_real_jmeter_ramp_matches_the_schedule(tmp_path):
    with serve(TargetConfig(latency_ms=1)) as base:
        port = base.rsplit(":", 1)[1]
        jtl = run_jmeter(FIXTURES / "jm_threads_ramp.jmx", {"port": port, "threads": 5, "ramp": 2, "loops": 3}, tmp_path)
    data = read_jtl(jtl)
    assert sum(r["threadName"].startswith("Merchants ") for r in data) == 15
    assert check_ramp(data, threads=5, ramp_up_s=2, group="Merchants") == []
