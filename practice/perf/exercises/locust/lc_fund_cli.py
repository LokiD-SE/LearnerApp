"""Build a headless Locust run from code: the run-time format, the command line and LOCUST_* environment
variables.

Every option is documented on the Locust "Configuration" page (Locust 2.47.0). Settings are read in this order,
each overriding the one before: ./pyproject.toml -> ./locust.conf -> --config file -> environment variables ->
command line arguments.

Implement the three functions; tests/locust/test_lc_fund_cli.py checks them and runs real Locust with what you build.
"""

from __future__ import annotations

import re  # noqa: F401 - you will need it


def parse_run_time(text: str) -> int:
    """TODO: seconds in a Locust time span, like Locust's own -t/--run-time parser:
    "20" -> 20 (a bare number is seconds), "20s" -> 20, "3m" -> 180, "2h" -> 7200, "1h20m" -> 4800,
    "3h30m10s" -> 12610. Raise ValueError for "", "10x", "1m2h", "abc"."""
    raise NotImplementedError


def headless_command(locustfile: str, host: str, users: int, spawn_rate: float, run_time: str, out_prefix: str, *,
                     locust: str = "locust", exit_code_on_error: int | None = None,
                     stop_timeout: int | None = None, user_classes: tuple[str, ...] = ()) -> list[str]:
    """TODO: return the argv list for a headless run that stops by itself and leaves machine-readable results:

    [locust, "-f", locustfile, "--headless", "-u", users, "-r", spawn_rate, "-t", run_time, "--host", host,
     "--csv", out_prefix, "--json-file", out_prefix, "--only-summary"]  (every item a str)

    then "--exit-code-on-error N" and "--stop-timeout N" only when given, and the user class names last.
    Raise ValueError if users < 1, spawn_rate <= 0, or run_time is not a positive time span."""
    raise NotImplementedError


def locust_env(options: dict[str, object]) -> dict[str, str]:
    """TODO: LOCUST_* environment variables for options named like their long flags (with or without "--"):
    {"spawn-rate": 5, "--headless": True} -> {"LOCUST_SPAWN_RATE": "5", "LOCUST_HEADLESS": "true"}.
    Booleans become "true"/"false"; everything else str()."""
    raise NotImplementedError
