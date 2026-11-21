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


def _hist(entry: dict) -> dict[int, int]:
    return {int(k): v for k, v in entry["response_times"].items()}


def percentile(response_times: dict, num_requests: int, fraction: float) -> int:
    hist = {int(k): v for k, v in response_times.items()}
    allowed = int(num_requests * fraction)
    processed = 0
    for rt in sorted(hist, reverse=True):
        processed += hist[rt]
        if num_requests - processed <= allowed:
            return rt
    return 0


def merge_entries(entries: list[dict]) -> dict:
    merged = {"method": entries[0]["method"], "name": entries[0]["name"], "num_requests": 0, "num_failures": 0,
              "total_response_time": 0.0, "min_response_time": None, "max_response_time": 0.0,
              "response_times": {}}
    for e in entries:
        merged["num_requests"] += e["num_requests"]
        merged["num_failures"] += e["num_failures"]
        merged["total_response_time"] += e["total_response_time"]
        lo = e["min_response_time"]
        if lo is not None and (merged["min_response_time"] is None or lo < merged["min_response_time"]):
            merged["min_response_time"] = lo
        merged["max_response_time"] = max(merged["max_response_time"], e["max_response_time"])
        for rt, n in _hist(e).items():
            merged["response_times"][rt] = merged["response_times"].get(rt, 0) + n
    return merged


def merge_workers(worker_dumps: list[list[dict]]) -> dict[str, dict]:
    by_name: dict[str, list[dict]] = {}
    for dump in worker_dumps:
        for e in dump:
            by_name.setdefault(e["name"], []).append(e)
    return {name: merge_entries(es) for name, es in by_name.items()}


def naive_percentile(worker_dumps: list[list[dict]], fraction: float) -> float:
    """The mistake: the mean of each worker's percentile over all of its requests."""
    values = []
    for dump in worker_dumps:
        total = merge_entries(dump)
        values.append(percentile(total["response_times"], total["num_requests"], fraction))
    return sum(values) / len(values)


def even_split(total_users: int, workers: int) -> list[int]:
    base, extra = divmod(total_users, workers)
    return [base + (1 if i < extra else 0) for i in range(workers)]
