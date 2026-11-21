"""Reading a step load: where does throughput stop growing, and what does the ceiling mean?

A step is the dict a closed-loop level run returns: ``{"clients": 8, "throughput": 191.5, "mean_ms": 40.7, ...}``
(throughput in requests per second, latency in milliseconds).
"""


def find_knee(steps, min_gain=0.10):
    """The client count after which more clients stop paying: the first step whose NEXT step raises throughput
    by less than ``min_gain`` (0.10 = 10%). Steps may arrive in any order; sort them by clients first.
    Return None when every step still gained at least ``min_gain`` (the system never saturated) or when there is
    only one step."""
    ordered = sorted(steps, key=lambda s: s["clients"])
    for current, following in zip(ordered, ordered[1:]):
        if following["throughput"] < current["throughput"] * (1 + min_gain):
            return current["clients"]
    return None


def wait_share(step, service_ms):
    """The share of the mean latency that is waiting rather than being served:
    (mean_ms - service_ms) / mean_ms, never below 0, rounded to 3 places."""
    return round(max(0.0, (step["mean_ms"] - service_ms) / step["mean_ms"]), 3)


def implied_slots(steps, service_ms):
    """How many requests the ceiling says are served at once (Little's law on the service station):
    highest throughput x service time, rounded to 1 place. Throughput is per second, service time in ms."""
    ceiling = max(s["throughput"] for s in steps)
    return round(ceiling * service_ms / 1000, 1)
