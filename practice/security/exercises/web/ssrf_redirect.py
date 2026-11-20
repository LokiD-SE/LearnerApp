"""Finding an open redirect from the Location header, without ever following it (WSTG-CLNT-04).

An open redirect sends the browser wherever a parameter says. The test never needs to follow the redirect:
read the ``Location`` header the server sent and ask whether a browser would leave the site's origin to
obey it. ``evil.example`` is under the reserved ``.example`` top-level domain (RFC 2606), so it can never
resolve to a real server; nothing in this module makes a request to it.

``send`` is any function that sends one value of the redirect parameter and returns ``(status, headers)`` -
the practice portal's ``portal_redirect_sender`` or an in-memory fake.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from urllib.parse import urljoin, urlsplit

import requests

Send = Callable[[str], tuple[int, dict[str, str]]]

REDIRECT_STATUSES = (301, 302, 303, 307, 308)
EVIL = "evil.example"

# (name, value) pairs; each is a different way of writing "go to another site".
PAYLOADS: tuple[tuple[str, str], ...] = (
    ("absolute", f"https://{EVIL}/"),
    ("protocol-relative", f"//{EVIL}/"),
    ("backslash", f"/\\{EVIL}/"),
    ("userinfo", f"https://shop.example@{EVIL}/"),
)


@dataclass(frozen=True)
class Finding:
    payload: str  # the payload name, e.g. "protocol-relative"
    value: str  # what was sent in the parameter
    location: str  # what the server put in the Location header


def redirect_location(status: int, headers: dict[str, str]) -> str | None:
    """The Location header of a redirect response, or None if this is not a redirect (or has no Location).

    Header names are case-insensitive: ``location`` and ``Location`` are the same header.
    """
    raise NotImplementedError("TODO: redirect_location")


def leaves_origin(location: str, base_url: str) -> bool:
    """True if a browser following ``location`` from a page at ``base_url`` would end up on another origin.

    Browsers treat a backslash as a slash in http(s) URLs and drop tab, CR and LF characters from a URL
    before parsing it (WHATWG URL Standard), so normalise those first, then resolve the location against the
    base and compare scheme, host and port.
    """
    raise NotImplementedError("TODO: leaves_origin")


def probe_open_redirect(send: Send, base_url: str, payloads: tuple[tuple[str, str], ...] = PAYLOADS) -> list[Finding]:
    """Every payload whose redirect leaves ``base_url``'s origin.

    First send a normal local path (``/settings``). If that does not redirect, or already leaves the origin,
    the parameter is not a redirect target or the test is meaningless: return an empty list. Then try each
    payload and keep those whose Location leaves the origin.
    """
    raise NotImplementedError("TODO: probe_open_redirect")


def portal_redirect_sender(base_url: str, timeout: float = 5.0) -> Send:
    """A ``send`` for the practice portal: GET ``/login?next=value``, never following the redirect."""

    def send(value: str) -> tuple[int, dict[str, str]]:
        r = requests.get(base_url + "/login", params={"next": value}, allow_redirects=False, timeout=timeout)
        return r.status_code, dict(r.headers)

    return send
