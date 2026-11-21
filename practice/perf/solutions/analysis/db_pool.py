"""Solution: pools, queues and caches as arithmetic."""

import heapq
import math
from collections import OrderedDict


def max_throughput(pool_size, hold_s):
    if pool_size < 1 or hold_s <= 0:
        raise ValueError("pool_size must be at least 1 and hold_s positive")
    return pool_size / hold_s


def pool_size_for(throughput_per_s, hold_s, utilisation=0.8):
    if throughput_per_s < 0 or hold_s <= 0 or not 0 < utilisation <= 1:
        raise ValueError("throughput >= 0, hold_s > 0, 0 < utilisation <= 1")
    # round() first: float noise just above 1 must not turn 1 connection into 2
    return max(1, math.ceil(round(throughput_per_s * hold_s / utilisation, 9)))


def starting_pool_size(cores, effective_spindles=0):
    return cores * 2 + effective_spindles


def simulate_pool(arrival_times, hold_s, pool_size):
    free_at = [0.0] * pool_size
    heapq.heapify(free_at)
    waits = []
    for arrival in arrival_times:
        earliest = heapq.heappop(free_at)
        start = max(arrival, earliest)
        waits.append(start - arrival)
        heapq.heappush(free_at, start + hold_s)
    return waits


def lru_hit_ratio(keys, capacity):
    keys = list(keys)
    if not keys:
        return 0.0
    cache = OrderedDict()
    hits = 0
    for key in keys:
        if key in cache:
            hits += 1
            cache.move_to_end(key)
        else:
            cache[key] = True
            if len(cache) > capacity:
                cache.popitem(last=False)
    return hits / len(keys)


def database_load(requests_per_s, hit_ratio):
    if not 0 <= hit_ratio <= 1:
        raise ValueError("hit_ratio must be between 0 and 1")
    return requests_per_s * (1 - hit_ratio)
