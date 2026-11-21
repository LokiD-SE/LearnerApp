"""SOLUTION - Probe a sign-in endpoint for a missing rate limit, with a control and no false positive.

``probe_login_limit`` sends repeated wrong sign-ins for ONE account that does not exist (so no real account is ever
locked or guessed), records the status codes, the ``Retry-After`` header and what a second account sees. ``assess``
turns that into a finding id or ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests
from sandpay_vuln import LOGIN_LIMIT

ACCOUNT_A = "limit-probe-a@shop-a.example"  # does not exist
ACCOUNT_B = "limit-probe-b@shop-a.example"  # does not exist


@dataclass(frozen=True)
class LimitResult:
    statuses: list[int]            # one status per attempt for account A, in order
    first_429_at: int | None       # 1-based number of the first attempt answered 429, or None
    retry_after: int | None        # the Retry-After header of that 429, in seconds, or None
    other_account_status: int      # status of one wrong sign-in for account B AFTER A hit the limit

    @property
    def limited(self) -> bool:
        return self.first_429_at is not None


def _wrong_login(base_url: str, email: str) -> requests.Response:
    return requests.post(base_url + "/api/login", json={"email": email, "password": "wrong"}, timeout=5)


def probe_login_limit(base_url: str, attempts: int = LOGIN_LIMIT + 3) -> LimitResult:
    if attempts < 2:
        raise ValueError("need at least two attempts to see a limit")
    statuses: list[int] = []
    first_429_at = None
    retry_after = None
    for number in range(1, attempts + 1):
        resp = _wrong_login(base_url, ACCOUNT_A)
        if number == 1 and resp.status_code != 401:
            raise RuntimeError(f"control failed: a wrong sign-in should answer 401, got {resp.status_code}")
        statuses.append(resp.status_code)
        if resp.status_code == 429 and first_429_at is None:
            first_429_at = number
            header = resp.headers.get("Retry-After")
            retry_after = int(header) if header is not None and header.isdigit() else None
    other = _wrong_login(base_url, ACCOUNT_B).status_code
    return LimitResult(statuses, first_429_at, retry_after, other)


def assess(result: LimitResult) -> str | None:
    """``"no-rate-limit"`` if nothing was ever limited, ``"shared-lockout"`` if the limit also blocked account B."""
    if not result.limited:
        return "no-rate-limit"
    if result.other_account_status == 429:
        return "shared-lockout"
    return None
