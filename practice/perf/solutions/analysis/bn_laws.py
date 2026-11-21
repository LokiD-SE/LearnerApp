"""Operational laws for finding the bottleneck of a request path (Lazowska et al., chapters 3 and 5).

Everything is per request, in seconds. ``demands`` maps a resource name to its service demand D_k: the total
time one request needs at that resource (visits x time per visit, divided by the number of identical servers).
"""


def demand(utilization, throughput):
    """The service demand law D = U / X: utilization (0 to 1) over throughput (requests per second)."""
    return utilization / throughput


def bottleneck(demands):
    """The resource with the largest demand; a tie goes to the name that sorts first."""
    top = max(demands.values())
    return min(name for name, d in demands.items() if d == top)


def max_throughput(demands):
    """The throughput ceiling 1 / D_max in requests per second."""
    return 1 / max(demands.values())


def knee_population(demands, think_s):
    """N* = (D + Z) / D_max: the number of users at which the light-load and heavy-load bounds cross,
    where D is the sum of all demands and Z the think time in seconds."""
    return (sum(demands.values()) + think_s) / max(demands.values())


def throughput_bounds(demands, think_s, n):
    """(lower, upper) bound on throughput with n users: lower = n / (n D + Z),
    upper = min(1 / D_max, n / (D + Z))."""
    total = sum(demands.values())
    lower = n / (n * total + think_s)
    upper = min(1 / max(demands.values()), n / (total + think_s))
    return lower, upper


def what_if(demands, name, factor):
    """Multiply the demand of one resource by ``factor`` (0.5 = twice as fast) and return
    (new bottleneck name, new throughput ceiling). The input is not changed."""
    changed = {**demands, name: demands[name] * factor}
    return bottleneck(changed), max_throughput(changed)
