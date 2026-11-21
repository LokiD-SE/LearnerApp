"""Exercise: pools, queues and caches as arithmetic.

A connection pool is a queue in front of ``pool_size`` servers; a cache is a filter in front of the database.
Both can be reasoned about with a few lines of code before you spend a load test on them.

Times are in seconds unless a name ends in ``_ms``.
"""


def max_throughput(pool_size, hold_s):
    """TODO: the most requests per second a pool can serve when every request holds a connection ``hold_s``
    seconds: ``pool_size / hold_s``. Raise ValueError if ``pool_size`` is below 1 or ``hold_s`` is not positive."""
    raise NotImplementedError("pool_size / hold_s")


def pool_size_for(throughput_per_s, hold_s, utilisation=0.8):
    """TODO: the smallest whole pool size that serves ``throughput_per_s`` requests per second when each request
    holds a connection ``hold_s`` seconds, and keeps the pool no more than ``utilisation`` busy on average
    (Little's law: connections in use = throughput x hold time; divide by the target utilisation; round UP).
    Raise ValueError for a negative throughput, a hold time that is not positive, or a utilisation outside (0, 1]."""
    raise NotImplementedError("ceil(throughput x hold / utilisation)")


def starting_pool_size(cores, effective_spindles=0):
    """TODO: the PostgreSQL project's starting point for the number of active connections, quoted on the HikariCP
    "About Pool Sizing" page: ``(core_count * 2) + effective_spindle_count``."""
    raise NotImplementedError("cores * 2 + spindles")


def simulate_pool(arrival_times, hold_s, pool_size):
    """TODO: how long each request waits for a connection. ``arrival_times`` is sorted; every request holds a
    connection for ``hold_s`` seconds; a free connection goes to the longest-waiting request (FIFO). Return one
    wait (seconds) per request, in arrival order.

    Hint: keep a heap of the times at which each connection becomes free (all 0 at the start).
    """
    raise NotImplementedError("a heap of connection free-times")


def lru_hit_ratio(keys, capacity):
    """TODO: the fraction of ``keys`` (a sequence of lookups) found in an LRU cache of ``capacity`` entries that
    starts empty. On a miss the key is added; when the cache is over capacity the least recently used entry is
    dropped; a hit makes the key the most recently used. Return 0.0 for an empty sequence."""
    raise NotImplementedError("an OrderedDict is enough")


def database_load(requests_per_s, hit_ratio):
    """TODO: the lookups per second that reach the database behind a cache with this hit ratio.
    Raise ValueError if ``hit_ratio`` is outside [0, 1]."""
    raise NotImplementedError("requests x (1 - hit ratio)")
