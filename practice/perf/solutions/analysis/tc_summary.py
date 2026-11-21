"""Solution: put JMeter's and Locust's results into the same summary.

Both tools record every request, failed ones included, and both keep failed requests' times in their response-time
statistics, so the percentiles here are over *every* request. All percentiles take a fraction (0.95), as Locust's own
function does.
"""

import math


def percentile(values, fraction):
    """Nearest rank on exact values: the ceil(fraction x n)-th smallest, the smallest value for fraction 0."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def bucket(ms):
    """Locust's rounding of a response time before it is counted (stats.bucket_response_time, Locust 2.47.0):
    under 100 ms it only rounds to a whole millisecond, then to the nearest 10 below 1000, 100 below 10000 and
    1000 above - about two significant digits."""
    if ms < 100:
        return round(ms)
    if ms < 1000:
        return int(round(ms, -1))
    if ms < 10000:
        return int(round(ms, -2))
    return int(round(ms, -3))


def locust_percentile(histogram, requests, fraction):
    """Locust's rule (stats.calculate_response_time_percentile): walk the bucketed times from the slowest down and
    return the first one at which the requests still slower-or-equal number at least requests - int(requests x
    fraction). ``histogram`` maps a bucketed time (an int or a string, as in the JSON file) to its count."""
    if requests <= 0:
        return 0
    allowed = int(requests * fraction)
    seen = 0
    for ms in sorted((int(k) for k in histogram), reverse=True):
        seen += histogram[ms] if ms in histogram else histogram[str(ms)]
        if requests - seen <= allowed:
            return ms
    return 0


def _label_stats(requests, failures, p50, p95):
    return {"requests": requests, "failures": failures, "p50": p50, "p95": p95}


def summarise_jtl(rows):
    """{requests, failures, rps, labels: {label: {requests, failures, p50, p95}}} from the rows of a CSV JTL
    (``timeStamp`` = start in ms, ``elapsed`` in ms, ``label``, ``success`` = "true" / "false").
    ``rps`` is the rate over the active span with the fence post corrected: (n - 1) / (last start - first start)."""
    by_label = {}
    for row in rows:
        by_label.setdefault(row["label"], []).append(row)
    labels = {}
    for label, group in sorted(by_label.items()):
        times = [int(r["elapsed"]) for r in group]
        failed = sum(1 for r in group if r["success"] != "true")
        labels[label] = _label_stats(len(group), failed, percentile(times, 0.5), percentile(times, 0.95))
    starts = [int(r["timeStamp"]) for r in rows]
    span = (max(starts) - min(starts)) / 1000 if starts else 0
    n = len(rows)
    return {"requests": n, "failures": sum(v["failures"] for v in labels.values()),
            "rps": round((n - 1) / span, 1) if span > 0 else 0.0, "labels": labels}


def summarise_locust(entries):
    """The same summary from Locust's totals (``--json-file``, keyed by name; an "Aggregated" row, if the file has one, is skipped).
    Percentiles use Locust's own rounding and rule, so they are bucketed, not exact."""
    labels = {}
    first, last = None, None
    for name, e in sorted(entries.items()):
        if name == "Aggregated":
            continue
        n = e["num_requests"]
        labels[name] = _label_stats(n, e["num_failures"], locust_percentile(e["response_times"], n, 0.5),
                                    locust_percentile(e["response_times"], n, 0.95))
        first = e["start_time"] if first is None else min(first, e["start_time"])
        last = e["last_request_timestamp"] if last is None else max(last, e["last_request_timestamp"])
    n = sum(v["requests"] for v in labels.values())
    span = (last - first) if labels else 0
    return {"requests": n, "failures": sum(v["failures"] for v in labels.values()),
            "rps": round((n - 1) / span, 1) if span > 0 else 0.0, "labels": labels}


def mix(summary):
    """Each label's share of all requests, rounded to 3 decimals."""
    total = summary["requests"]
    return {label: round(v["requests"] / total, 3) for label, v in summary["labels"].items()} if total else {}


def same_scenario(a, b, tolerance=0.02):
    """Reasons two summaries do not describe the same scenario ([] when they do): a label only one has, or a share
    of the request mix that differs by more than ``tolerance`` (absolute, 0.02 = two percentage points)."""
    problems = []
    ma, mb = mix(a), mix(b)
    for label in sorted(set(ma) | set(mb)):
        if label not in ma:
            problems.append(f"{label}: only in the second run")
        elif label not in mb:
            problems.append(f"{label}: only in the first run")
        elif abs(ma[label] - mb[label]) > tolerance:
            problems.append(f"{label}: {ma[label]:.1%} of the first run, {mb[label]:.1%} of the second")
    return problems
