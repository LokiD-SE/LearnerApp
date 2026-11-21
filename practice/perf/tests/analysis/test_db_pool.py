import pytest
from analysis.db_pool import (
    database_load,
    lru_hit_ratio,
    max_throughput,
    pool_size_for,
    simulate_pool,
    starting_pool_size,
)

pytestmark = pytest.mark.exercise


def test_max_throughput_is_size_over_hold_time():
    assert max_throughput(4, 0.02) == pytest.approx(200)  # the lesson's pool of 4 with 20 ms per request
    assert max_throughput(1, 0.5) == pytest.approx(2)


def test_max_throughput_rejects_nonsense():
    for size, hold in ((0, 0.02), (4, 0), (4, -1)):
        with pytest.raises(ValueError):
            max_throughput(size, hold)


def test_pool_size_for_uses_littles_law_and_rounds_up():
    # 200 req/s x 0.02 s = 4 connections busy on average; at 80 % utilisation that is 5
    assert pool_size_for(200, 0.02) == 5
    # 100 req/s x 0.03 s = 3 busy; 3 / 0.8 = 3.75 -> 4
    assert pool_size_for(100, 0.03) == 4
    # exactly full is allowed at utilisation 1.0
    assert pool_size_for(200, 0.02, utilisation=1.0) == 4


def test_pool_size_for_is_never_below_one_connection():
    assert pool_size_for(0, 0.02) == 1
    assert pool_size_for(1, 0.001) == 1


def test_pool_size_for_ignores_floating_point_noise():
    # 7 x 0.1 / 0.7 comes out a hair above 1 in floating point, but the answer is exactly 1 connection
    assert pool_size_for(7, 0.1, utilisation=0.7) == 1
    assert pool_size_for(6, 0.2, utilisation=0.6) == 2


def test_pool_size_for_rejects_nonsense():
    for args in ((-1, 0.02, 0.8), (10, 0, 0.8), (10, 0.02, 0), (10, 0.02, 1.5)):
        with pytest.raises(ValueError):
            pool_size_for(*args)


def test_starting_pool_size_is_the_postgresql_rule():
    assert starting_pool_size(4, 1) == 9  # the HikariCP page's own example: ((4 * 2) + 1)
    assert starting_pool_size(8) == 16


def test_big_enough_pool_means_no_waiting():
    arrivals = [n * 0.5 for n in range(20)]
    assert simulate_pool(arrivals, 1.0, 2) == [0.0] * 20


def test_one_connection_and_double_the_rate_builds_a_growing_queue():
    arrivals = [n * 0.5 for n in range(6)]  # a request every 0.5 s, each needs 1.0 s
    assert simulate_pool(arrivals, 1.0, 1) == [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]


def test_simultaneous_burst_is_served_in_waves():
    waits = simulate_pool([0.0] * 6, 1.0, 2)  # six at once, two at a time
    assert waits == [0.0, 0.0, 1.0, 1.0, 2.0, 2.0]


def test_queue_drains_after_a_burst():
    arrivals = [0.0] * 4 + [10.0]
    waits = simulate_pool(arrivals, 1.0, 2)
    assert waits[-1] == 0.0 and waits[:4] == [0.0, 0.0, 1.0, 1.0]


def test_no_requests_no_waits():
    assert simulate_pool([], 1.0, 3) == []


def test_lru_hit_ratio_on_a_small_sequence():
    keys = ["a", "b", "a", "c", "a", "b"]
    # capacity 2: a miss, b miss, a hit, c miss (evicts b), a hit, b miss -> 2 hits of 6
    assert lru_hit_ratio(keys, 2) == pytest.approx(2 / 6)


def test_lru_hit_ratio_capacity_extremes():
    keys = [1, 2, 3, 1, 2, 3]
    assert lru_hit_ratio(keys, 3) == pytest.approx(3 / 6)  # everything fits: only the first lookups miss
    assert lru_hit_ratio(keys, 2) == 0.0  # a loop one entry longer than the cache never hits under LRU
    assert lru_hit_ratio([], 5) == 0.0


def test_a_hit_refreshes_recency():
    # capacity 2: a, b, a (hit, a is newest), c evicts b, a is still there
    assert lru_hit_ratio(["a", "b", "a", "c", "a"], 2) == pytest.approx(2 / 5)


def test_database_load_is_the_misses():
    assert database_load(1000, 0.578) == pytest.approx(422)
    assert database_load(1000, 0.0) == 1000
    assert database_load(1000, 1.0) == 0


def test_database_load_rejects_a_bad_ratio():
    with pytest.raises(ValueError):
        database_load(1000, 1.5)
