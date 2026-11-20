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
    """TODO: POST /login (form fields email, password); return the ``sid`` cookie. Raise RuntimeError if the
    status is not 200 or no sid is set."""
    raise NotImplementedError("sign_in")


def is_valid(base_url: str, sid: str, timeout: float = 5) -> bool:
    """TODO: True when GET /account with this id as the ``sid`` cookie answers 200."""
    raise NotImplementedError("is_valid")


def verify_logout(base_url: str, email: str, password: str, timeout: float = 5) -> LogoutResult:
    """TODO: Sign in, check the session works, POST /logout with it, then:
    - ``cookie_cleared``: the logout's Set-Cookie empties or expires ``sid`` (empty value, Max-Age=0 or Expires);
    - ``old_id_rejected``: replaying the old id now fails;
    - ``vulnerable``: the old id still works."""
    raise NotImplementedError("verify_logout")


def verify_timeouts(base_url: str, email: str, password: str, wait: Callable[[float], None],
                    idle_limit_s: float, absolute_limit_s: float, margin_s: float = 60,
                    timeout: float = 5) -> TimeoutResult:
    # Idle: one silent gap just over the limit.
    """TODO: Idle: sign in, ``wait(idle_limit_s + margin_s)`` once, replay -> ``idle_enforced`` if rejected.
    Absolute: sign in again; repeatedly ``wait(idle_limit_s / 2)`` and check the session, until it is
    rejected or more than ``absolute_limit_s + margin_s`` has passed. ``absolute_enforced`` = it was rejected;
    ``observed_lifetime_s`` = the waiting time added up when you stopped."""
    raise NotImplementedError("verify_timeouts")
