"""Session fixation and exposed session ids - WSTG-SESS-03 and WSTG-SESS-04, as automated probes.

``probe_fixation`` follows the WSTG fixation test: take the session id the site issues before sign-in, sign in
presenting it, and see whether (a) the site rotated the id and (b) the pre-login id now opens the signed-in
account. Only (b) proves impact: an attacker who planted that id could now use the victim's session.

``probe_url_session`` checks the exchange mechanism: is the id written into links, and does the server accept
it from the URL (``?sid=``) instead of only from the cookie? A URL id leaks through history, logs and the
Referer header, and is the easy way to plant a fixed id.

Run only against systems you own or have written permission to test; the tests use a loopback practice service.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests

COOKIE = "sid"


@dataclass
class FixationResult:
    pre_login_id: str | None  # id issued by GET /login before signing in
    post_login_id: str | None  # id in force after signing in (new Set-Cookie, or the same one)
    rotated: bool  # a different id after sign-in
    old_id_authenticated: bool  # the pre-login id opens /account after the victim signed in
    vulnerable: bool  # True when the pre-login id is authenticated - the fixation impact


@dataclass
class UrlSessionResult:
    id_in_links: bool  # the sign-in page writes the session id into a URL
    accepted_from_url: bool  # /account answers 200 for ?sid=<id> with no cookie
    vulnerable: bool


def session_id_from(response: requests.Response) -> str | None:
    """The ``sid`` value from the response's Set-Cookie, or None when it sets none (or clears it)."""
    value = response.cookies.get(COOKIE)
    return value or None


def probe_fixation(base_url: str, email: str, password: str, timeout: float = 5) -> FixationResult:
    pre = requests.get(f"{base_url}/login", timeout=timeout)
    pre_id = session_id_from(pre)
    if pre_id is None:
        # No pre-login session: nothing to fix in place, so fixation through this route is not possible.
        return FixationResult(None, None, False, False, False)
    login = requests.post(f"{base_url}/login", data={"email": email, "password": password},
                          cookies={COOKIE: pre_id}, timeout=timeout)
    if login.status_code != 200:
        raise RuntimeError(f"sign-in failed: {login.status_code} {login.text[:200]}")
    post_id = session_id_from(login) or pre_id  # no new Set-Cookie means the old cookie stays in force
    rotated = post_id != pre_id
    replay = requests.get(f"{base_url}/account", cookies={COOKIE: pre_id}, timeout=timeout)
    old_ok = replay.status_code == 200
    return FixationResult(pre_id, post_id, rotated, old_ok, old_ok)


def probe_url_session(base_url: str, email: str, password: str, timeout: float = 5) -> UrlSessionResult:
    page = requests.get(f"{base_url}/login", timeout=timeout)
    sid = session_id_from(page)
    in_links = bool(sid) and re.search(rf"[?&]{COOKIE}={re.escape(sid)}", page.text) is not None
    login = requests.post(f"{base_url}/login", data={"email": email, "password": password},
                          cookies={COOKIE: sid} if sid else None, timeout=timeout)
    if login.status_code != 200:
        raise RuntimeError(f"sign-in failed: {login.status_code} {login.text[:200]}")
    signed_in = session_id_from(login) or sid
    # The id only in the URL - no Cookie header at all.
    by_url = requests.get(f"{base_url}/account", params={COOKIE: signed_in}, timeout=timeout)
    accepted = by_url.status_code == 200
    return UrlSessionResult(in_links, accepted, in_links or accepted)
