"""What a load generator costs, and how many you need.

A *run* is a dict as the lesson's capture script records it: ``users``, ``requests``, ``wall_s``, ``cpu_user_s``,
``cpu_sys_s`` (CPU seconds the operating system charged to the tool, all its threads together) and ``rss_peak_mb``.
Complete every function.
"""


def cpu_seconds(run):
    """User plus system CPU seconds."""
    raise NotImplementedError("TODO")


def cores_busy(run):
    """Average number of CPU cores the tool kept busy: CPU seconds / wall seconds (can be above 1)."""
    raise NotImplementedError("TODO")


def cpu_per_1000(run):
    """CPU seconds per 1000 requests, start-up cost included."""
    raise NotImplementedError("TODO")


def marginal_cpu_per_1000(run, startup):
    """CPU seconds per 1000 requests with the fixed cost taken out: (CPU of the run - CPU of the ``startup`` run)
    over (requests of the run - requests of the ``startup`` run), times 1000."""
    raise NotImplementedError("TODO")


def mb_per_user(small, big):
    """Extra peak memory (``rss_peak_mb``) per extra virtual user between a run with few users and one with many."""
    raise NotImplementedError("TODO")


def median_of(runs, key):
    """Median of one number across repeated runs; ``key`` is a run key (a string) or a function of a run."""
    raise NotImplementedError("TODO")


def generators_needed(target_rps, rps_per_core, max_busy=0.7):
    """How many single-core generators for ``target_rps`` when each may be at most ``max_busy`` busy.
    At least 1; a whole number (round up)."""
    raise NotImplementedError("TODO")


def cheapest(setups, key):
    """The name of the setup with the smallest median of ``key`` (a run key or function); ties go to the name that
    sorts first. ``setups`` maps a setup name to its list of repeated runs."""
    raise NotImplementedError("TODO")
