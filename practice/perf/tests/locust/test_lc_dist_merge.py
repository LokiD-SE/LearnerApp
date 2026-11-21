"""Checks exercises/locust/lc_dist_merge.py against a real run: two workers and a master (8 users, 6 seconds),
with the workers' own statistics and the master's merged statistics both captured (see lc_dist_fixture.py)."""

import copy

import pytest
from lc_dist_fixture import SAMPLE_MASTER_STATS, SAMPLE_WORKER_DUMPS, load_exercise

pytestmark = pytest.mark.exercise

m = load_exercise("locust/lc_dist_merge.py")


def _hist(entry):
    return {int(k): v for k, v in entry["response_times"].items()}


def test_percentile_follows_locusts_algorithm():
    assert m.percentile({"10": 6, "20": 4}, 10, 0.5) == 10
    assert m.percentile({10: 5, 20: 5}, 10, 0.95) == 20
    assert m.percentile({"1": 99, "500": 1}, 100, 0.95) == 1
    assert m.percentile({"1": 99, "500": 1}, 100, 0.99) == 500
    assert m.percentile({}, 0, 0.95) == 0


def test_the_merge_reproduces_the_masters_numbers_exactly():
    merged = m.merge_workers(SAMPLE_WORKER_DUMPS)
    assert set(merged) == {e["name"] for e in SAMPLE_MASTER_STATS}
    for e in SAMPLE_MASTER_STATS:
        got = merged[e["name"]]
        assert got["num_requests"] == e["num_requests"], e["name"]
        assert got["num_failures"] == e["num_failures"]
        assert got["total_response_time"] == pytest.approx(e["total_response_time"], abs=0.01)
        assert got["min_response_time"] == pytest.approx(e["min_response_time"], abs=0.01)
        assert got["max_response_time"] == pytest.approx(e["max_response_time"], abs=0.01)
        assert {int(k): v for k, v in got["response_times"].items()} == _hist(e)


def test_merged_percentiles_match_the_master():
    merged = m.merge_workers(SAMPLE_WORKER_DUMPS)
    for e in SAMPLE_MASTER_STATS:
        got = merged[e["name"]]
        for f in (0.5, 0.95, 0.99):
            assert m.percentile(got["response_times"], got["num_requests"], f) == \
                m.percentile(e["response_times"], e["num_requests"], f)


def test_merging_does_not_change_its_input_and_handles_one_worker():
    before = copy.deepcopy(SAMPLE_WORKER_DUMPS)
    m.merge_workers(SAMPLE_WORKER_DUMPS)
    assert SAMPLE_WORKER_DUMPS == before
    solo = m.merge_workers([SAMPLE_WORKER_DUMPS[1]])
    assert set(solo) == {"/health"}
    assert solo["/health"]["num_requests"] == SAMPLE_WORKER_DUMPS[1][0]["num_requests"]


def test_a_missing_minimum_is_ignored():
    a = {"method": "GET", "name": "/x", "num_requests": 1, "num_failures": 0, "total_response_time": 5.0,
         "min_response_time": None, "max_response_time": 5.0, "response_times": {"5": 1}}
    b = {**a, "min_response_time": 7.0, "max_response_time": 7.0, "response_times": {"7": 1}, "total_response_time": 7.0}
    out = m.merge_entries([a, b])
    assert out["min_response_time"] == 7.0 and out["max_response_time"] == 7.0 and out["num_requests"] == 2


def test_averaging_the_workers_95th_percentiles_is_wrong_by_a_lot():
    merged = m.merge_workers(SAMPLE_WORKER_DUMPS)
    flat = m.merge_entries([{**e, "name": "all"} for e in merged.values()])
    true_p95 = m.percentile(flat["response_times"], flat["num_requests"], 0.95)
    naive = m.naive_percentile(SAMPLE_WORKER_DUMPS, 0.95)
    assert true_p95 >= 90  # the 72 slow reports are 10 % of all requests, so the real p95 is a report time
    assert naive < true_p95 - 30, (naive, true_p95)


@pytest.mark.parametrize("total, workers, expected", [(10, 3, [4, 3, 3]), (8, 2, [4, 4]), (2, 4, [1, 1, 0, 0]),
                                                      (7, 1, [7]), (0, 3, [0, 0, 0])])
def test_even_split(total, workers, expected):
    assert m.even_split(total, workers) == expected
