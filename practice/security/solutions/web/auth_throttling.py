"""A bounded password-guessing probe that tests login throttling (WSTG-ATHN-03, weak lock out mechanism).

A tester does not need to "crack" anything to prove missing throttling: send a small, fixed number of wrong
passwords for ONE account you are allowed to test and watch whether the server ever pushes back (429, a lockout
message, a growing delay). The probe is deliberately small and refuses anything but the local practice portal.

    result = probe_login_throttling(base_url, "alice@shop-a.example", ["guess-1", "guess-2", ...], max_attempts=10)
    classify(result)   # "missing-rate-limit" | "throttled" | "password-found" | "inconclusive"
"""

from __future__ import annotations

import urllib.parse

import requests

LOOPBACK = {"127.0.0.1", "localhost", "::1"}
MAX_ATTEMPTS_CAP = 20  # a probe, not an attack: never more than this, whatever the caller asks for


def _require_loopback(base_url: str) -> None:
    host = urllib.parse.urlsplit(base_url).hostname
    if host not in LOOPBACK:
        raise ValueError(f"refusing {host!r}: this probe only runs against the local practice portal")


def probe_login_throttling(base_url: str, email: str, wordlist: list[str], max_attempts: int = 10,
                           path: str = "/api/login", session: requests.Session | None = None) -> dict:
    """Tries up to ``max_attempts`` passwords from ``wordlist`` for one ``email``, in order, and stops at the
    first sign of throttling (429) or at the first success (200).

    Returns ``{"attempts", "statuses", "throttled", "throttled_after", "retry_after", "found"}``:
    ``throttled_after`` is how many attempts were answered before the first 429 (None if never throttled),
    ``retry_after`` the 429's Retry-After header, ``found`` the password that worked (None if none did).
    """
    _require_loopback(base_url)
    if not 1 <= max_attempts <= MAX_ATTEMPTS_CAP:
        raise ValueError(f"max_attempts must be between 1 and {MAX_ATTEMPTS_CAP}")
    http = session or requests.Session()
    statuses: list[int] = []
    result = {"attempts": 0, "statuses": statuses, "throttled": False, "throttled_after": None,
              "retry_after": None, "found": None}
    for password in wordlist[:max_attempts]:
        r = http.post(base_url + path, json={"email": email, "password": password}, timeout=10)
        statuses.append(r.status_code)
        result["attempts"] = len(statuses)
        if r.status_code == 429:
            result.update(throttled=True, throttled_after=len(statuses) - 1, retry_after=r.headers.get("Retry-After"))
            break
        if r.status_code == 200:
            result["found"] = password
            break
    return result


def classify(result: dict, min_attempts: int = 10) -> str:
    """Turns a probe result into a finding.

    - ``throttled``: the server answered 429 at some point.
    - ``password-found``: a password worked before any throttling - report the weak password AND the missing
      throttling evidence you have.
    - ``missing-rate-limit``: at least ``min_attempts`` wrong passwords were all answered normally.
    - ``inconclusive``: fewer attempts than ``min_attempts`` and no throttling - not enough evidence either way.
    """
    if result["throttled"]:
        return "throttled"
    if result["found"] is not None:
        return "password-found"
    if result["attempts"] >= min_attempts:
        return "missing-rate-limit"
    return "inconclusive"
