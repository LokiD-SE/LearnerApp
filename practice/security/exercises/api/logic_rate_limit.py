"""EXERCISE - Probe a sign-in endpoint for a missing rate limit, with a control and no false positive.

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
    """Send ``attempts`` wrong sign-ins for ACCOUNT_A, then one for ACCOUNT_B, and fill in a ``LimitResult``.

    Raise ``ValueError`` when ``attempts`` < 2. Raise ``RuntimeError`` if the FIRST wrong sign-in is not answered
    with 401 - without that control a later "no 429" proves nothing. ``retry_after`` is the integer header value of
    the first 429, or ``None`` when there is no header.
    """
    raise NotImplementedError("TODO: implement probe_login_limit")


def assess(result: LimitResult) -> str | None:
    """``"no-rate-limit"`` if nothing was ever limited, ``"shared-lockout"`` if the limit also blocked account B,
    otherwise ``None``."""
    raise NotImplementedError("TODO: implement assess")
