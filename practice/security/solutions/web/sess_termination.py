"""Session termination - WSTG-SESS-06 (logout) and WSTG-SESS-07 (idle and absolute timeouts), as probes.

The rule both pages share: ending a session is the SERVER's job. A cleared cookie proves nothing - replay the
old id and the server must refuse it.

Waiting hours in a test is not practical, so the timeout checks take a ``wait(seconds)`` function. Against the
practice service it moves a fake clock; against a real system it would be ``time.sleep`` inside an agreed
test window. The method is the WSTG black-box one either way:

- idle: sign in, stay silent for longer than the idle limit, replay the id;
- absolute: sign in, keep the session busy with a request more often than the idle limit, until past the
  absolute limit, then replay. A black-box test can only show that a session lived LONGER than the window - so
  report the observed lifetime, not "there is no absolute timeout".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import requests

COOKIE = "sid"


@dataclass
class LogoutResult:
    cookie_cleared: bool  # logout response tells the browser to drop the cookie
    old_id_rejected: bool  # replaying the pre-logout id gets 401
    vulnerable: bool  # the old id still works after logout


@dataclass
class TimeoutResult:
    idle_enforced: bool  # silent for idle_limit + margin -> rejected
    absolute_enforced: bool  # kept busy past absolute_limit + margin -> rejected at or before the end
    observed_lifetime_s: float  # how long the busy session stayed valid (the whole window if never cut)


def sign_in(base_url: str, email: str, password: str, timeout: float = 5) -> str:
    r = requests.post(f"{base_url}/login", data={"email": email, "password": password}, timeout=timeout)
    if r.status_code != 200 or not r.cookies.get(COOKIE):
        raise RuntimeError(f"sign-in failed: {r.status_code} {r.text[:200]}")
    return r.cookies[COOKIE]


def is_valid(base_url: str, sid: str, timeout: float = 5) -> bool:
    return requests.get(f"{base_url}/account", cookies={COOKIE: sid}, timeout=timeout).status_code == 200


def verify_logout(base_url: str, email: str, password: str, timeout: float = 5) -> LogoutResult:
    sid = sign_in(base_url, email, password, timeout)
    if not is_valid(base_url, sid, timeout):
        raise RuntimeError("the new session does not work - check the sign-in before testing logout")
    out = requests.post(f"{base_url}/logout", cookies={COOKIE: sid}, timeout=timeout)
    set_cookie = out.headers.get("Set-Cookie", "").lower()
    cleared = set_cookie.startswith(f"{COOKIE}=;") or "max-age=0" in set_cookie or "expires=" in set_cookie
    rejected = not is_valid(base_url, sid, timeout)
    return LogoutResult(cleared, rejected, not rejected)


def verify_timeouts(base_url: str, email: str, password: str, wait: Callable[[float], None],
                    idle_limit_s: float, absolute_limit_s: float, margin_s: float = 60,
                    timeout: float = 5) -> TimeoutResult:
    # Idle: one silent gap just over the limit.
    sid = sign_in(base_url, email, password, timeout)
    wait(idle_limit_s + margin_s)
    idle_enforced = not is_valid(base_url, sid, timeout)

    # Absolute: a fresh session kept busy (gaps of half the idle limit) for the whole window.
    sid = sign_in(base_url, email, password, timeout)
    window = absolute_limit_s + margin_s
    step = idle_limit_s / 2
    elapsed = 0.0
    alive = True
    while elapsed < window:
        wait(step)
        elapsed += step
        if not is_valid(base_url, sid, timeout):
            alive = False
            break
    return TimeoutResult(idle_enforced, not alive, elapsed)
