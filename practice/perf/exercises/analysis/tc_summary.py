"""Put JMeter's and Locust's results into the same summary - then check they describe the same scenario.

Both tools record every request, failed ones included, and both keep failed requests' times in their response-time
statistics, so the percentiles here are over *every* request. All percentiles take a fraction (0.95), as Locust's own
function does.

Complete every function. The lesson "JMeter, Locust and other tools compared" explains each rule.
"""


def percentile(values, fraction):
    """Nearest rank on exact values: the ceil(fraction x n)-th smallest (the smallest for fraction 0);
    None for an empty list."""
    raise NotImplementedError("TODO: sort, pick the nearest rank")


def bucket(ms):
    """Locust's rounding before it counts a response time: under 100 ms round to a whole millisecond; under 1000
    round to the nearest 10; under 10000 to the nearest 100; otherwise to the nearest 1000 (always an int)."""
    raise NotImplementedError("TODO: the four ranges")


def locust_percentile(histogram, requests, fraction):
    """Locust's rule. ``histogram`` maps a bucketed time (int or str key, as in the JSON file) to its count.
    allowed = int(requests x fraction); walk the times from the slowest down, adding counts; return the first time
    where ``requests - seen <= allowed``. Return 0 when there are no requests."""
    raise NotImplementedError("TODO: walk the buckets from the top")


def summarise_jtl(rows):
    """From the rows of a CSV JTL (``timeStamp`` start ms, ``elapsed`` ms, ``label``, ``success`` 'true'/'false'):
    {"requests": n, "failures": f, "rps": r, "labels": {label: {"requests", "failures", "p50", "p95"}}}.
    ``rps`` = (n - 1) / ((last start - first start) / 1000) rounded to 1 decimal, 0.0 for a zero span.
    Labels are in sorted order; percentiles are over every row of the label (use ``percentile``)."""
    raise NotImplementedError("TODO: group by label")


def summarise_locust(entries):
    """The same dict from Locust's totals: ``entries`` maps a request name to its stats dict (``num_requests``,
    ``num_failures``, ``response_times`` histogram, ``start_time``, ``last_request_timestamp``). Skip an
    "Aggregated" entry if there is one. Percentiles use ``locust_percentile``; ``rps`` = (n - 1) / (latest last_request_timestamp -
    earliest start_time)."""
    raise NotImplementedError("TODO: same shape as summarise_jtl")


def mix(summary):
    """Each label's share of all requests, rounded to 3 decimals ({} when there are no requests)."""
    raise NotImplementedError("TODO: requests / total")


def same_scenario(a, b, tolerance=0.02):
    """Reasons two summaries do not describe the same scenario ([] when they do), in sorted label order:
    ``"<label>: only in the second run"``, ``"<label>: only in the first run"`` or
    ``"<label>: 25.0% of the first run, 30.0% of the second"`` (shares differing by more than ``tolerance``)."""
    raise NotImplementedError("TODO: compare the two mixes")
