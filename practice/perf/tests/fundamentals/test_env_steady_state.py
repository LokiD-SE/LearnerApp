import pytest
from env_fixture import serve_cold_start, write_plan
from fundamentals.env_steady_state import Bucket, bucket, load_samples, steady_start, summarise
from load_tools import jmeter_home, read_jtl, run_jmeter

pytestmark = pytest.mark.exercise


def rows(*samples, failed=()):
    return [{"timeStamp": str(t), "elapsed": str(e), "success": "false" if (t, e) in failed else "true"}
            for t, e in samples]


def test_load_samples_keeps_successes_sorted():
    data = rows((2000, 5), (1000, 40), (1500, 9), failed={(1500, 9)})
    assert load_samples(data) == [(1000, 40), (2000, 5)]


def test_bucket_groups_by_width_from_the_first_sample():
    samples = [(1000, 40), (1100, 42), (1600, 10), (2600, 6), (2700, 4)]
    assert bucket(samples, 500) == [Bucket(0, 2, 41.0), Bucket(1, 1, 10.0), Bucket(3, 2, 5.0)]
    assert bucket([], 500) == []


def B(*medians):
    return [Bucket(i, 10, float(m)) for i, m in enumerate(medians)]


def test_steady_start_skips_the_warm_up():
    assert steady_start(B(40, 38, 20, 6, 5, 5, 6, 5), window=3, tolerance=0.5) == 3


def test_a_single_dip_does_not_count_as_settled():
    # bucket 1 looks settled, but bucket 2 is still slow, so the window starting at 1 fails.
    assert steady_start(B(40, 5, 30, 5, 6, 5), window=3, tolerance=0.5) == 3


def test_a_run_that_is_settled_from_the_start():
    assert steady_start(B(5, 6, 5, 5), window=3, tolerance=0.5) == 0


def test_steady_start_needs_enough_buckets_and_a_settled_end():
    with pytest.raises(ValueError):
        steady_start(B(5, 5), window=3)
    with pytest.raises(ValueError):
        steady_start(B(1, 10, 100), window=3, tolerance=0.1)


def test_summarise_counts_the_steady_part_only():
    assert summarise(B(40, 5, 6, 5), 1) == (30, 5.0)


@pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")
def test_real_jmeter_run_shows_and_skips_the_warm_up(tmp_path):
    with serve_cold_start(warm_after=200, cold_ms=40, warm_ms=5) as base:
        port = base.rsplit(":", 1)[1]
        jtl = run_jmeter(write_plan(tmp_path), {"port": port, "threads": 4, "loops": 250}, tmp_path / "out")
    buckets = bucket(load_samples(read_jtl(jtl)), 250)
    start = steady_start(buckets, window=3, tolerance=0.5)
    assert start >= 1                                   # the first buckets are the cold phase
    assert buckets[0].median_ms > 2 * summarise(buckets, start)[1]
    assert sum(b.count for b in buckets) == 1000
