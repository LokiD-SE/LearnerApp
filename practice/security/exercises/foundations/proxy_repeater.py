"""A command-line "Repeater": take a request copied from a proxy's history, change one thing, send it again and
compare the responses - the manual loop behind Burp Repeater and ZAP's Requester.

You write:

- ``parse_raw_request(raw)`` - a raw HTTP/1.1 request (as a proxy shows it) into a ``RecordedRequest``;
- ``with_path_segment(req, old, new)`` - the same request with one whole path segment swapped;
- ``diff(a, b)`` - what changed between two responses, as short lines a tester can paste into a finding;
- ``probe_idor(req, own_id, other_id, owner_field)`` - replay a "read my object" request with another
  user's object id and report a finding only when the server hands over someone else's object.

``send(req)`` is given. Only loopback targets are sent to (practice safety).
"""

from __future__ import annotations

import http.client
import json
import urllib.parse
from dataclasses import dataclass, field, replace

LOOPBACK = ("127.0.0.1", "localhost", "::1")


@dataclass(frozen=True)
class RecordedRequest:
    method: str
    url: str  # absolute, e.g. http://127.0.0.1:8765/api/payments/pay_1001
    headers: tuple[tuple[str, str], ...]
    body: bytes = b""


@dataclass(frozen=True)
class Reply:
    status: int
    headers: dict[str, str]  # lower-case names
    body: bytes

    def json(self) -> object | None:
        try:
            return json.loads(self.body)
        except (ValueError, UnicodeDecodeError):
            return None


@dataclass
class Finding:
    title: str
    original: Reply
    replayed: Reply
    changes: list[str] = field(default_factory=list)


def parse_raw_request(raw: str) -> RecordedRequest:
    """Parse a raw request such as::

        GET /api/payments/pay_1001 HTTP/1.1
        Host: 127.0.0.1:8765
        Authorization: Bearer eyJ...

    - Lines may end in CRLF or LF. The head ends at the first empty line; what follows is the body (encoded as
      UTF-8). A ``Content-Length`` header, if present, cuts the body to that many bytes.
    - The URL is ``http://<Host><request-target>`` for origin-form; an absolute-form target (proxy style) is
      used as it is.
    - Header names keep their case and order; values are stripped of surrounding spaces. The ``Host`` header
      stays in ``headers``.
    - Raise ``ValueError`` for a malformed request line or header line, or an origin-form request without Host.
    """
    raise NotImplementedError("TODO: implement parse_raw_request - see the docstring")


def with_path_segment(req: RecordedRequest, old: str, new: str) -> RecordedRequest:
    """The same request with every path segment equal to ``old`` replaced by ``new``. Only whole segments
    change (``pay_1001`` does not touch ``pay_10010``); the query string is kept. Raise ``ValueError`` if no
    segment equals ``old``."""
    raise NotImplementedError("TODO: implement with_path_segment - see the docstring")


def send(req: RecordedRequest, timeout: float = 5) -> Reply:
    """Send ``req`` exactly as recorded (given)."""
    split = urllib.parse.urlsplit(req.url)
    if split.hostname not in LOOPBACK:
        raise ValueError("practice repeater only sends to loopback addresses")
    conn = http.client.HTTPConnection(split.hostname, split.port or 80, timeout=timeout)
    path = split.path + ("?" + split.query if split.query else "")
    conn.putrequest(req.method, path, skip_host=True, skip_accept_encoding=True)
    for name, value in req.headers:
        if name.lower() != "content-length":
            conn.putheader(name, value)
    if req.body:
        conn.putheader("Content-Length", str(len(req.body)))
    conn.endheaders(req.body or None)
    resp = conn.getresponse()
    reply = Reply(resp.status, {k.lower(): v for k, v in resp.getheaders()}, resp.read())
    conn.close()
    return reply


def diff(a: Reply, b: Reply) -> list[str]:
    """Differences from ``a`` to ``b``, in this order:

    - ``"status 200 -> 404"`` if the status differs;
    - if both bodies are JSON objects: one line per top-level key, sorted by key -
      ``"json merchant_id: 'm_100' -> 'm_200'"`` (values shown with ``repr``), ``"json api_secret: removed"``,
      ``"json error: added 'payment not found'"``;
    - otherwise, if the bodies differ: ``"body changed (120 -> 30 bytes)"``.
    Identical replies give ``[]``.
    """
    raise NotImplementedError("TODO: implement diff - see the docstring")


def probe_idor(req: RecordedRequest, own_id: str, other_id: str, owner_field: str = "merchant_id") -> Finding | None:
    """Replay ``req`` (a request for the caller's own object ``own_id``) with ``other_id`` in its path.

    Return a ``Finding`` titled ``"IDOR: <other_id> readable by the owner of <own_id>"`` (with both replies and
    ``diff(original, replayed)`` as ``changes``) only when:
    - the original request succeeds (2xx) with a JSON object that has ``owner_field``, and
    - the replayed request also succeeds (2xx) with a JSON object whose ``owner_field`` differs.
    Return ``None`` otherwise - a 403/404 for the other id is the access control working, and a replay that
    returns the caller's own object is not a leak. Raise ``ValueError`` if the original request fails, since
    then the probe proves nothing.
    """
    raise NotImplementedError("TODO: implement probe_idor - see the docstring")
