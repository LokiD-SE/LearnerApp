"""Build a headless Locust run from code: the run-time format, the command line and LOCUST_* environment
variables - reference solution.

Every option is documented on the Locust "Configuration" page (Locust 2.47.0). Settings are read in this order,
each overriding the one before: ./pyproject.toml -> ./locust.conf -> --config file -> environment variables ->
command line arguments.
"""

from __future__ import annotations

import re

_TIMESPAN = re.compile(r"((?P<hours>\d+?)h)?((?P<minutes>\d+?)m)?((?P<seconds>\d+?)s)?")


def parse_run_time(text: str) -> int:
    """Seconds in a Locust time span: "20", "20s", "3m", "2h", "1h20m", "3h30m10s". A bare number is seconds."""
    if not text:
        raise ValueError("empty run time")
    if re.fullmatch(r"\d+", text):
        return int(text)
    match = _TIMESPAN.fullmatch(text)
    if not match or not any(match.groupdict().values()):
        raise ValueError(f"invalid run time {text!r}; valid: 20, 20s, 3m, 2h, 1h20m, 3h30m10s")
    parts = {k: int(v) for k, v in match.groupdict().items() if v}
    return parts.get("hours", 0) * 3600 + parts.get("minutes", 0) * 60 + parts.get("seconds", 0)


def headless_command(locustfile: str, host: str, users: int, spawn_rate: float, run_time: str, out_prefix: str, *,
                     locust: str = "locust", exit_code_on_error: int | None = None,
                     stop_timeout: int | None = None, user_classes: tuple[str, ...] = ()) -> list[str]:
    """The argv for a headless run that ends by itself and leaves machine-readable results:
    ``<prefix>_stats.csv`` (and friends) from --csv and ``<prefix>.json`` from --json-file."""
    if users < 1:
        raise ValueError("users must be at least 1")
    if spawn_rate <= 0:
        raise ValueError("spawn_rate must be positive")
    if parse_run_time(run_time) <= 0:
        raise ValueError("run_time must be positive - without it a headless run never stops")
    argv = [locust, "-f", str(locustfile), "--headless", "-u", str(users), "-r", str(spawn_rate), "-t", run_time,
            "--host", host, "--csv", str(out_prefix), "--json-file", str(out_prefix), "--only-summary"]
    if exit_code_on_error is not None:
        argv += ["--exit-code-on-error", str(exit_code_on_error)]
    if stop_timeout is not None:
        argv += ["--stop-timeout", str(stop_timeout)]
    return argv + list(user_classes)


def locust_env(options: dict[str, object]) -> dict[str, str]:
    """LOCUST_* environment variables for options named like their long flags: {"spawn-rate": 5} ->
    {"LOCUST_SPAWN_RATE": "5"}; booleans become "true"/"false"."""
    env = {}
    for name, value in options.items():
        key = "LOCUST_" + name.removeprefix("--").replace("-", "_").upper()
        env[key] = str(value).lower() if isinstance(value, bool) else str(value)
    return env
