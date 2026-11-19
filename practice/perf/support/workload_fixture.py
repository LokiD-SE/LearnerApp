"""A synthetic, deterministic SandPay API access log for the workload-modelling lesson (Track K).

One day (17 November 2026, UTC) of traffic in a simple combined-style format::

    203.0.113.24 - merchant-7 [17/Nov/2026:12:03:41 +0000] "GET /v1/payments?limit=20 HTTP/1.1" 200 812 0.034

Fields: client IP, ``-``, authenticated client id (``-`` if none), timestamp, request line, status, response
bytes, duration in seconds. The day contains what real logs contain and a workload model must handle:

- merchant sessions: a token request, then 1-8 API calls drawn from a fixed mix, arriving on a daily
  (diurnal) curve with a lunchtime and an evening peak;
- skew: a few merchants send most of the traffic (Zipf-like weights);
- a monitoring probe (``GET /health`` every 10 s from ``10.0.0.5``) that is not user traffic;
- a nightly batch: ``merchant-3`` pulls settlement reports in a 3-minute burst at 02:00;
- some errors (401, 404, 500) and a few malformed lines.

Everything is synthetic (IPs from the documentation ranges in RFC 5737). ``generate_access_log()`` returns the
same lines for the same seed on every machine.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

DAY = datetime(2026, 11, 17, tzinfo=timezone.utc)
# Relative traffic per hour of the day (UTC): quiet night, lunchtime and evening peaks.
HOURLY_SHAPE = (1, 1, 1, 1, 1, 2, 3, 5, 7, 8, 9, 11, 13, 12, 10, 9, 9, 10, 12, 13, 11, 7, 4, 2)
SESSIONS_PER_DAY = 6000
SESSION_MIX = (  # (endpoint template, weight) for calls after the token request
    ("GET /v1/payments?limit=20", 55),
    ("GET /v1/payments/{id}", 27),
    ("POST /v1/payments", 15),
    ("GET /v1/reports/settlement", 3),
)
MERCHANTS = 50
BATCH_REPORTS = 600


def _fmt(ts: datetime) -> str:
    return ts.strftime("%d/%b/%Y:%H:%M:%S +0000")


def _ip(rng: random.Random) -> str:
    return f"203.0.113.{rng.randint(1, 254)}" if rng.random() < 0.5 else f"198.51.100.{rng.randint(1, 254)}"


def generate_access_log(seed: int = 2026) -> list[str]:
    rng = random.Random(seed)
    zipf = [1 / (rank ** 1.2) for rank in range(1, MERCHANTS + 1)]
    endpoints, weights = zip(*SESSION_MIX)
    entries: list[tuple[datetime, str]] = []

    total_shape = sum(HOURLY_SHAPE)
    for hour, share in enumerate(HOURLY_SHAPE):
        for _ in range(round(SESSIONS_PER_DAY * share / total_shape)):
            start = DAY + timedelta(hours=hour, seconds=rng.uniform(0, 3600))
            merchant = f"merchant-{rng.choices(range(1, MERCHANTS + 1), zipf)[0]}"
            ip = _ip(rng)
            t = start
            line = f'{ip} - {merchant} [{_fmt(t)}] "POST /auth/token HTTP/1.1" 200 96 {rng.uniform(0.01, 0.03):.3f}'
            entries.append((t, line))
            for _ in range(rng.randint(1, 8)):
                t += timedelta(seconds=rng.uniform(2, 40))  # think time between calls
                template = rng.choices(endpoints, weights)[0]
                method, path = template.split(" ")
                path = path.replace("{id}", f"pay_{rng.randint(100001, 100750)}")
                status, size, dur = 200, rng.randint(300, 2400), rng.lognormvariate(-3.3, 0.5)
                if method == "POST":
                    status, size, dur = 201, 182, dur * 2
                if "reports" in path:
                    dur *= 10
                r = rng.random()
                if r < 0.01:
                    status, size = 500, 48
                elif r < 0.02 and "{id}" in template:
                    status, size = 404, 31
                elif r < 0.025:
                    status, size = 401, 45
                entries.append((t, f'{ip} - {merchant} [{_fmt(t)}] "{method} {path} HTTP/1.1" {status} {size} {dur:.3f}'))

    # Monitoring: GET /health every 10 seconds all day - real requests, but not user workload.
    for i in range(0, 86400, 10):
        t = DAY + timedelta(seconds=i)
        entries.append((t, f'10.0.0.5 - - [{_fmt(t)}] "GET /health HTTP/1.1" 200 15 0.001'))

    # Nightly batch: merchant-3 pulls settlement reports in a 3-minute burst at 02:00.
    for i in range(BATCH_REPORTS):
        t = DAY + timedelta(hours=2, seconds=rng.uniform(0, 180))
        entries.append((t, f'198.51.100.77 - merchant-3 [{_fmt(t)}] "GET /v1/reports/settlement HTTP/1.1" 200 2048 '
                           f'{rng.uniform(0.2, 0.6):.3f}'))

    # A few malformed lines, as real logs have (truncated writes, a scanner sending garbage).
    for i, junk in enumerate(('203.0.113.9 - - [17/Nov/2026:03:14:07 +0000] "\\x16\\x03\\x01" 400 0 0.000',
                              "203.0.113.10 - merchant-2 [17/Nov/2026:11:00:0",
                              "")):
        entries.append((DAY + timedelta(hours=3 + i * 4), junk))

    entries.sort(key=lambda e: e[0])
    return [line for _, line in entries]


def write_access_log(path: Path, seed: int = 2026) -> Path:
    path.write_text("\n".join(generate_access_log(seed)) + "\n")
    return path


if __name__ == "__main__":
    lines = generate_access_log()
    print(len(lines), "lines")
    print("\n".join(lines[:3]))
