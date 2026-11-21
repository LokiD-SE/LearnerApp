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


def master_command(locustfile: str, host: str, users: int, spawn_rate: float, run_time: str, workers: int,
                   port: int, out_prefix: str, *, locust: str = "locust") -> list[str]:
    """TODO: argv (all str) for the master of a headless run with --expect-workers, on loopback:

    [locust, "-f", locustfile, "--master", "--master-bind-host", "127.0.0.1", "--master-bind-port", port,
     "--headless", "--expect-workers", workers, "-u", users, "-r", spawn_rate, "-t", run_time, "--host", host,
     "--csv", out_prefix, "--json-file", out_prefix, "--only-summary"]

    Raise ValueError if workers < 1, users < workers, spawn_rate <= 0, run_time is "" or "0", or port is
    outside 1024-65535."""
    raise NotImplementedError


def worker_command(locustfile: str, port: int, *, locust: str = "locust") -> list[str]:
    """TODO: argv for one worker that connects to the loopback master on ``port``:

    [locust, "-f", locustfile, "--worker", "--master-host", "127.0.0.1", "--master-port", port,
     "--loglevel", "WARNING"]"""
    raise NotImplementedError


def processes_command(locustfile: str, host: str, users: int, spawn_rate: float, run_time: str, processes: int,
                      port: int, out_prefix: str, *, locust: str = "locust") -> list[str]:
    """TODO: argv for the one-command form (a master plus ``processes`` forked workers), loopback only:

    [locust, "-f", locustfile, "--headless", "--processes", processes, "--master-bind-host", "127.0.0.1",
     "--master-bind-port", port, "--master-port", port, "-u", users, "-r", spawn_rate, "-t", run_time,
     "--host", host, "--csv", out_prefix, "--json-file", out_prefix, "--only-summary"]

    Same ValueError rules as master_command (``processes`` plays the part of ``workers``)."""
    raise NotImplementedError


def audit(argv: list[str]) -> list[str]:
    """TODO: the problem ids found in a Locust command line, in this order, or [] for none:

    - "master-not-loopback": a master (``--master``, or ``--processes`` without ``--worker``) whose
      ``--master-bind-host`` is missing or not one of LOOPBACK_HOSTS
    - "worker-master-not-loopback": a worker (``--worker``) whose ``--master-host`` is given and is not in
      LOOPBACK_HOSTS (absent means localhost, which is fine)
    - "no-expect-workers": a headless ``--master`` without ``--expect-workers``
    - "port-mismatch": ``--processes`` (no ``--worker``) with a ``--master-bind-port`` different from
      ``--master-port``; an absent port means Locust's default, 5557
    - "no-run-time": a ``--headless`` command without ``-t`` or ``--run-time``"""
    raise NotImplementedError
