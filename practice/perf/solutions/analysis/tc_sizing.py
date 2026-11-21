"""Solution: what a load generator costs, and how many you need.

A *run* is a dict as the lesson's capture script records it: ``users``, ``requests``, ``wall_s``, ``cpu_user_s``,
``cpu_sys_s`` (CPU seconds the operating system charged to the tool, all its threads together) and ``rss_peak_mb``.
"""

import math
import statistics


def cpu_seconds(run):
    """User plus system CPU seconds."""
    return run["cpu_user_s"] + run["cpu_sys_s"]


def cores_busy(run):
    """Average number of CPU cores the tool kept busy: CPU seconds / wall seconds (can be above 1)."""
    return cpu_seconds(run) / run["wall_s"]


def cpu_per_1000(run):
    """CPU seconds per 1000 requests, start-up cost included."""
    return cpu_seconds(run) / run["requests"] * 1000


def marginal_cpu_per_1000(run, startup):
    """CPU seconds per 1000 requests with the fixed cost taken out: (CPU of the run - CPU of the start-up run) over
    (requests of the run - requests of the start-up run), times 1000."""
    return (cpu_seconds(run) - cpu_seconds(startup)) / (run["requests"] - startup["requests"]) * 1000


def mb_per_user(small, big):
    """Extra peak memory per extra virtual user between a run with few users and one with many."""
    return (big["rss_peak_mb"] - small["rss_peak_mb"]) / (big["users"] - small["users"])


def median_of(runs, key):
    """Median of one number across repeated runs; ``key`` is a run key or a function of a run."""
    values = [key(r) if callable(key) else r[key] for r in runs]
    return statistics.median(values)


def generators_needed(target_rps, rps_per_core, max_busy=0.7):
    """How many single-core generators for ``target_rps`` when each may be at most ``max_busy`` busy
    (a generator near 100 % starts to distort the measurement). At least 1; a whole number."""
    return max(1, math.ceil(target_rps / (rps_per_core * max_busy)))


def cheapest(setups, key):
    """The name of the setup with the smallest median of ``key`` (a run key or function); ties go to the name that
    sorts first. ``setups`` maps a setup name to its list of repeated runs."""
    return min(sorted(setups), key=lambda name: median_of(setups[name], key))
