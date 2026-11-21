"""Operational laws for finding the bottleneck of a request path (Lazowska et al., chapters 3 and 5).

Everything is per request, in seconds. ``demands`` maps a resource name to its service demand D_k: the total
time one request needs at that resource (visits x time per visit, divided by the number of identical servers).
"""


def demand(utilization, throughput):
    """The service demand law D = U / X: utilization (0 to 1) over throughput (requests per second).

    TODO: one line.
    """
    raise NotImplementedError


def bottleneck(demands):
    """The resource with the largest demand; a tie goes to the name that sorts first.

    TODO: look at max(demands.values()).
    """
    raise NotImplementedError


def max_throughput(demands):
    """The throughput ceiling 1 / D_max in requests per second.

    TODO: the largest demand saturates first.
    """
    raise NotImplementedError


def knee_population(demands, think_s):
    """N* = (D + Z) / D_max: the number of users at which the light-load and heavy-load bounds cross,
    where D is the sum of all demands and Z the think time in seconds.

    TODO: one line.
    """
    raise NotImplementedError


def throughput_bounds(demands, think_s, n):
    """(lower, upper) bound on throughput with n users: lower = n / (n D + Z),
    upper = min(1 / D_max, n / (D + Z)).

    TODO: D is the sum of the demands.
    """
    raise NotImplementedError


def what_if(demands, name, factor):
    """Multiply the demand of one resource by ``factor`` (0.5 = twice as fast) and return
    (new bottleneck name, new throughput ceiling). The input is not changed.

    TODO: build a changed copy, then reuse bottleneck() and max_throughput().
    """
    raise NotImplementedError
