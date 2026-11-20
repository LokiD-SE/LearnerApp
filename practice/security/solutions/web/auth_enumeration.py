"""User enumeration through the login response (WSTG-IDNT-04 / OWASP Authentication Cheat Sheet).

Send the same wrong password for an email you know exists and for one you know does not, several times each,
interleaved, and compare the three signals an attacker can see: the status code, the body and the response time.
Any difference lets an attacker test a list of emails and keep the ones that exist.

    known = [observe(base, "alice@shop-a.example") ...]   # or check_enumeration(...) to do it all
    compare(known, unknown)  # {"enumerable": True, "signals": ["timing"], ...}
"""

from __future__ import annotations

import statistics
import time
import urllib.parse
from dataclasses import dataclass

import requests

LOOPBACK = {"127.0.0.1", "localhost", "::1"}
WRONG_PASSWORD = "not-the-password-0"


@dataclass(frozen=True)
class Observation:
    status: int
    body: str
    ms: float


def observe(http: requests.Session, url: str, email: str, password: str = WRONG_PASSWORD) -> Observation:
    """One login attempt: status, body text and wall-clock time in milliseconds. (Given - not the exercise.)"""
    start = time.perf_counter()
    r = http.post(url, json={"email": email, "password": password}, timeout=10)
    return Observation(r.status_code, r.text, (time.perf_counter() - start) * 1000)


def compare(known: list[Observation], unknown: list[Observation], min_delta_ms: float = 25.0,
            min_ratio: float = 3.0) -> dict:
    """Compares observations for a known and an unknown email and names each signal that differs.

    - ``status``: the sets of status codes differ.
    - ``message``: the sets of response bodies differ.
    - ``timing``: the median times differ by at least ``min_delta_ms`` AND the slower median is at least
      ``min_ratio`` times the faster one (floored at 1 ms), so noise of a few milliseconds is not a finding.
      Either direction counts.
    """
    if not known or not unknown:
        raise ValueError("need at least one observation for each email")
    signals = []
    if {o.status for o in known} != {o.status for o in unknown}:
        signals.append("status")
    if {o.body for o in known} != {o.body for o in unknown}:
        signals.append("message")
    k = statistics.median(o.ms for o in known)
    u = statistics.median(o.ms for o in unknown)
    slow, fast = max(k, u), min(k, u)
    if slow - fast >= min_delta_ms and slow >= min_ratio * max(fast, 1.0):
        signals.append("timing")
    return {"enumerable": bool(signals), "signals": signals,
            "known_median_ms": round(k, 1), "unknown_median_ms": round(u, 1)}


def check_enumeration(base_url: str, known_email: str, unknown_email: str, samples: int = 4,
                      path: str = "/api/login") -> dict:
    """Runs ``samples`` interleaved attempts per email (known, unknown, known, ...) and compares them.

    Interleaving keeps slow drift (a busy machine, a warming cache) from looking like a difference between the
    two emails. A 429 means the server throttled the probe: the result is inconclusive
    (``{"enumerable": None, "rate_limited": True, ...}``), not "safe".
    """
    host = urllib.parse.urlsplit(base_url).hostname
    if host not in LOOPBACK:
        raise ValueError(f"refusing {host!r}: this check only runs against the local practice portal")
    http = requests.Session()
    url = base_url + path
    known: list[Observation] = []
    unknown: list[Observation] = []
    for _ in range(samples):
        for email, bucket in ((known_email, known), (unknown_email, unknown)):
            o = observe(http, url, email)
            if o.status == 429:
                return {"enumerable": None, "signals": [], "rate_limited": True}
            bucket.append(o)
    return {**compare(known, unknown), "rate_limited": False}
