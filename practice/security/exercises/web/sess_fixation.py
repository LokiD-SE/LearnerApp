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
    # TODO: Return the ``sid`` cookie value the response sets, or None when it sets none or an empty value
    # (a logout's clearing cookie). Hint: ``response.cookies``.
    raise NotImplementedError("session_id_from")


def probe_fixation(base_url: str, email: str, password: str, timeout: float = 5) -> FixationResult:
    """TODO: 1. GET /login with no cookie and read the pre-login id (none -> return a not-vulnerable result).
    2. POST /login with the credentials, presenting that id as the ``sid`` cookie; raise RuntimeError if not 200.
    3. The post-login id is the new Set-Cookie value, or the old id if none was set.
    4. Replay GET /account with the PRE-login id: 200 means fixation (``vulnerable``)."""
    raise NotImplementedError("probe_fixation")


def probe_url_session(base_url: str, email: str, password: str, timeout: float = 5) -> UrlSessionResult:
    """TODO: 1. GET /login: is the issued id written into the page as ``sid=<id>`` in a link?
    2. Sign in (raise RuntimeError if not 200) and take the signed-in id.
    3. GET /account with the id ONLY as a query parameter (no Cookie). 200 means it is accepted from the URL.
    ``vulnerable`` = in links or accepted."""
    raise NotImplementedError("probe_url_session")
