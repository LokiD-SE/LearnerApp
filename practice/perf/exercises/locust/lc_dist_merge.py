"""What the master does with the workers' numbers: add them up, bucket by bucket, and only then read percentiles.

Each worker sends its own statistics; the master merges them. Counts and times add. Response times are kept as
a histogram (``response_times``: rounded milliseconds -> how many requests took that long), and histograms add
too. A percentile of the merged histogram is the percentile of all requests. The mean of the workers'
percentiles is not, because a worker that ran few requests counts as much as one that ran many.

Locust's own algorithm (``calculate_response_time_percentile`` in ``locust/stats.py``, Locust 2.47.0):

    num_of_request = int(num_requests * percent)
    processed_count = 0
    for response_time in sorted(response_times.keys(), reverse=True):
        processed_count += response_times[response_time]
        if num_requests - processed_count <= num_of_request:
            return response_time
    return 0

Entries are the dicts Locust serialises: method, name, num_requests, num_failures, total_response_time,
min_response_time, max_response_time, response_times (keys may be str when read from JSON).

Implement the five functions; tests/locust/test_lc_dist_merge.py checks them against a real two-worker run.
"""

from __future__ import annotations


def percentile(response_times: dict, num_requests: int, fraction: float) -> int:
    """TODO: Locust's algorithm above. ``response_times`` keys may be str ("13") or int; return an int
    (0 if the histogram is empty). percentile({"10": 6, "20": 4}, 10, 0.5) == 10."""
    raise NotImplementedError


def merge_entries(entries: list[dict]) -> dict:
    """TODO: merge entries for ONE request name (one per worker) into one entry with the same fields:
    method and name from the first; num_requests, num_failures and total_response_time summed;
    min_response_time the smallest (ignore None), max_response_time the largest; response_times
    the histograms added, keys as int."""
    raise NotImplementedError


def merge_workers(worker_dumps: list[list[dict]]) -> dict[str, dict]:
    """TODO: group every worker's entries by name and merge each group: {name: merged entry}."""
    raise NotImplementedError


def naive_percentile(worker_dumps: list[list[dict]], fraction: float) -> float:
    """TODO: the mistake, to measure it: for each worker, the percentile over ALL its requests (merge its
    entries, then percentile); return the plain mean of those per-worker numbers."""
    raise NotImplementedError


def even_split(total_users: int, workers: int) -> list[int]:
    """TODO: how many users each worker runs when Locust spreads them evenly: sizes differ by at most one,
    the larger ones first. even_split(10, 3) == [4, 3, 3]."""
    raise NotImplementedError
