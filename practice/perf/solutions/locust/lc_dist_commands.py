"""Command lines for a distributed Locust run on ONE machine, bound to the loopback interface.

Every flag is documented on the Locust "Distributed load generation" and "Running without the web UI" pages
(Locust 2.47.0). Two facts matter here:

- ``--master-bind-host`` defaults to ``*`` (all network interfaces), so a master started without it listens for
  workers on every interface of the machine.
- ``--processes N`` starts a master and N workers itself, but a non-default ``--master-bind-port`` must be
  repeated as ``--master-port`` so the forked workers look for the master on that port.

Implement the four functions; tests/locust/test_lc_dist_commands.py checks them and runs real Locust clusters
with what you build.
"""

from __future__ import annotations

LOOPBACK = "127.0.0.1"
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")


def _check(users: int, spawn_rate: float, run_time: str, port: int, workers: int) -> None:
    if workers < 1:
        raise ValueError("at least one worker")
    if users < workers:
        raise ValueError("fewer users than workers leaves a worker with nothing to do")
    if spawn_rate <= 0:
        raise ValueError("spawn_rate must be positive")
    if not run_time or run_time == "0":
        raise ValueError("a headless run needs a run time, or it never stops")
    if not 1024 <= port <= 65535:
        raise ValueError("port must be 1024-65535")


def master_command(locustfile: str, host: str, users: int, spawn_rate: float, run_time: str, workers: int,
                   port: int, out_prefix: str, *, locust: str = "locust") -> list[str]:
    _check(users, spawn_rate, run_time, port, workers)
    return [locust, "-f", locustfile, "--master", "--master-bind-host", LOOPBACK, "--master-bind-port", str(port),
            "--headless", "--expect-workers", str(workers), "-u", str(users), "-r", str(spawn_rate),
            "-t", run_time, "--host", host, "--csv", out_prefix, "--json-file", out_prefix, "--only-summary"]


def worker_command(locustfile: str, port: int, *, locust: str = "locust") -> list[str]:
    return [locust, "-f", locustfile, "--worker", "--master-host", LOOPBACK, "--master-port", str(port),
            "--loglevel", "WARNING"]


def processes_command(locustfile: str, host: str, users: int, spawn_rate: float, run_time: str, processes: int,
                      port: int, out_prefix: str, *, locust: str = "locust") -> list[str]:
    _check(users, spawn_rate, run_time, port, processes)
    return [locust, "-f", locustfile, "--headless", "--processes", str(processes), "--master-bind-host", LOOPBACK,
            "--master-bind-port", str(port), "--master-port", str(port), "-u", str(users), "-r", str(spawn_rate),
            "-t", run_time, "--host", host, "--csv", out_prefix, "--json-file", out_prefix, "--only-summary"]


def _value(argv: list[str], flag: str) -> str | None:
    for i, a in enumerate(argv[:-1]):
        if a == flag:
            return argv[i + 1]
    return None


def audit(argv: list[str]) -> list[str]:
    """Problem ids found in a Locust command line (an empty list means none):

    - ``master-not-loopback``: a master (``--master``, or ``--processes`` without ``--worker``) whose
      ``--master-bind-host`` is missing or not a loopback address
    - ``worker-master-not-loopback``: a worker whose ``--master-host`` is given and is not a loopback address
    - ``no-expect-workers``: a headless ``--master`` without ``--expect-workers``
    - ``port-mismatch``: ``--processes`` with a ``--master-bind-port`` that differs from ``--master-port``
      (an absent ``--master-port`` means 5557)
    - ``no-run-time``: a headless command without ``-t`` / ``--run-time``
    """
    problems: list[str] = []
    worker = "--worker" in argv
    processes = "--processes" in argv
    master = "--master" in argv or (processes and not worker)
    if master and _value(argv, "--master-bind-host") not in LOOPBACK_HOSTS:
        problems.append("master-not-loopback")
    if worker:
        mh = _value(argv, "--master-host")
        if mh is not None and mh not in LOOPBACK_HOSTS:
            problems.append("worker-master-not-loopback")
    if "--master" in argv and "--headless" in argv and "--expect-workers" not in argv:
        problems.append("no-expect-workers")
    if processes and not worker:
        bind = _value(argv, "--master-bind-port") or "5557"
        if bind != (_value(argv, "--master-port") or "5557"):
            problems.append("port-mismatch")
    if "--headless" in argv and not ({"-t", "--run-time"} & set(argv)):
        problems.append("no-run-time")
    return problems
