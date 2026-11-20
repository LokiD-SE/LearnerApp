"""Exercise - size a distributed JMeter run: how many threads really hit the system?

From the JMeter user manual, 13. Remote Testing: "The same test plan is run by all the servers. JMeter does not
distribute the load between servers, each runs the full test plan. So if you set 1000 Threads and have 6 JMeter
server, you end up injecting 6000 Threads."

So the thread count in the plan (usually ``${__P(threads,...)}``, set for every server with ``-Gthreads=...``)
is a PER-SERVER count. A learner who wants 1,000 virtual users on 4 servers sends ``-Gthreads=250``, not 1000.

How many threads one load generator can drive is something you measure (a calibration run with the generator's
CPU, memory and network watched), not something you look up. The manual's step-by-step tutorial gives only a
rough guide: "A single JMeter client running on a 2-3 GHz CPU (recent CPU) can handle 1000-2000 threads
depending on the type of test."
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunSize:
    servers: int  # how many JMeter servers (load generators) to start
    threads_per_server: int  # the value to send with -Gthreads=...
    total_threads: int  # what the system under test really gets
    overshoot: int  # total_threads - target_threads (0 when the target divides evenly)


def total_threads(threads_per_server: int, servers: int) -> int:
    """Threads injected by ``servers`` servers that each run a plan with ``threads_per_server`` threads.
    ``servers == 0`` means a plain local (non-remote) run: the plan's threads, once.
    Raises ValueError for negative values."""
    raise NotImplementedError("TODO: total_threads")


def threads_per_server(target_threads: int, servers: int) -> int:
    """The -Gthreads value that gives exactly ``target_threads`` across ``servers`` servers.
    Raises ValueError if the target does not divide evenly (say so - don't silently round) or a count is below 1."""
    raise NotImplementedError("TODO: threads_per_server")


def size_run(target_threads: int, max_threads_per_server: int) -> RunSize:
    """The fewest servers that keep each one at or under ``max_threads_per_server`` (your measured limit), with
    the threads spread as evenly as one -G value allows: every server runs the same plan, so they all get the same
    count, rounded UP so the target is reached. Example: 1000 threads, limit 300 -> 4 servers x 250, no overshoot;
    1000 threads, limit 400 -> 3 servers x 334 = 1002, overshoot 2. Raises ValueError for counts below 1."""
    raise NotImplementedError("TODO: size_run")
