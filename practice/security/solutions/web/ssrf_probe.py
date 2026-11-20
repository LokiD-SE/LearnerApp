"""Finding server-side request forgery in a "send a test webhook" feature (WSTG-INPV-19, API7:2023).

The feature takes a URL from the client and makes the *server* fetch it. Two safe ways to prove it:

* **In-band.** Point the URL at something only the server can reach (an internal admin page) and look for
  that page's content in the answer - WSTG: "Use the loopback interface to access content restricted to the
  host only."
* **Blind.** When the answer shows nothing, point the URL at a listener you run yourself and look for the
  hit - WSTG: "the SSRF may also manifest in a blind manner".

Both only *read*. Nothing here sends a payload at a system you do not own: the practice portal only ever
fetches loopback addresses, and the listener is yours.

``send`` is any function that posts one URL to the feature and returns ``(status, body_text)``.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

import requests

Send = Callable[[str], tuple[int, str]]


class Listener(Protocol):
    """What the blind probe needs from a listener you control (see support/ssrf_fixture.py)."""

    def url(self, token: str) -> str: ...

    def saw(self, token: str) -> bool: ...


@dataclass(frozen=True)
class Finding:
    technique: str  # "in-band" or "blind"
    url: str  # the URL the server was asked to fetch
    evidence: str  # what proves the server fetched it


def classify(status: int, body: str) -> str:
    """Sorts one answer from the webhook feature into a label.

    * ``"rejected"``     - 4xx: the server refused the URL (a validation error).
    * ``"fetched"``      - 200 and the JSON says ``delivered`` is true: the server made the request.
    * ``"not-fetched"``  - 200 but ``delivered`` is false (or the body is not JSON): the server answered
                           without making the request.
    * ``"unreachable"``  - 5xx: the server tried and failed (closed port, DNS error, timeout).
    """
    if 400 <= status < 500:
        return "rejected"
    if status >= 500:
        return "unreachable"
    try:
        data = json.loads(body)
    except ValueError:
        return "not-fetched"
    return "fetched" if isinstance(data, dict) and data.get("delivered") is True else "not-fetched"


def probe_ssrf(send: Send, internal_url: str, marker: str) -> Finding | None:
    """In-band proof: ask the server to fetch ``internal_url`` and look for ``marker`` in the answer.

    ``marker`` is text that only the internal page contains. Report a finding only if the answer is
    ``fetched`` and the marker is in the body: a refusal, a "delivered: false" or a generic error that merely
    echoes the URL is not proof.
    """
    status, body = send(internal_url)
    if classify(status, body) != "fetched" or marker not in body:
        return None
    return Finding("in-band", internal_url, f"HTTP {status}: the answer contains {marker!r}")


def probe_blind(send: Send, listener: Listener) -> Finding | None:
    """Blind proof: ask the server to fetch a URL on your own listener and check the listener saw it.

    Use a fresh random token so a hit cannot be left over from another probe. The server's answer is ignored
    - it may show nothing at all; the only evidence is the hit.
    """
    token = uuid.uuid4().hex[:12]
    url = listener.url(token)
    send(url)
    if not listener.saw(token):
        return None
    return Finding("blind", url, f"the listener received GET /cb/{token}")


def portal_webhook_sender(base_url: str, token: str, timeout: float = 8.0) -> Send:
    """A ``send`` for the practice portal: POST /api/webhooks/test with a bearer token."""

    def send(url: str) -> tuple[int, str]:
        r = requests.post(base_url + "/api/webhooks/test", json={"url": url},
                          headers={"Authorization": f"Bearer {token}"}, timeout=timeout)
        return r.status_code, r.text

    return send
