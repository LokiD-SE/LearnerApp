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
    text = raw.replace("\r\n", "\n")
    head, _, body_text = text.partition("\n\n")
    lines = head.split("\n")
    parts = lines[0].strip().split(" ")
    if len(parts) != 3 or not parts[2].startswith("HTTP/"):
        raise ValueError(f"malformed request line: {lines[0]!r}")
    method, target, _ = parts
    headers: list[tuple[str, str]] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        name, sep, value = line.partition(":")
        if not sep or not name.strip() or name != name.strip():
            raise ValueError(f"malformed header line: {line!r}")
        headers.append((name, value.strip()))
    body = body_text.encode()
    for name, value in headers:
        if name.lower() == "content-length":
            body = body[: int(value)]
    if target.startswith("/"):
        host = next((v for n, v in headers if n.lower() == "host"), None)
        if not host:
            raise ValueError("origin-form request without a Host header")
        url = f"http://{host}{target}"
    else:
        url = target
    return RecordedRequest(method, url, tuple(headers), body)


def with_path_segment(req: RecordedRequest, old: str, new: str) -> RecordedRequest:
    """The same request with every path segment equal to ``old`` replaced by ``new``. Only whole segments
    change (``pay_1001`` does not touch ``pay_10010``); the query string is kept. Raise ``ValueError`` if no
    segment equals ``old``."""
    split = urllib.parse.urlsplit(req.url)
    segments = split.path.split("/")
    if old not in segments:
        raise ValueError(f"no path segment equals {old!r} in {split.path!r}")
    path = "/".join(new if s == old else s for s in segments)
    return replace(req, url=urllib.parse.urlunsplit(split._replace(path=path)))


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
    out: list[str] = []
    if a.status != b.status:
        out.append(f"status {a.status} -> {b.status}")
    ja, jb = a.json(), b.json()
    if isinstance(ja, dict) and isinstance(jb, dict):
        for key in sorted(set(ja) | set(jb)):
            if key not in jb:
                out.append(f"json {key}: removed")
            elif key not in ja:
                out.append(f"json {key}: added {jb[key]!r}")
            elif ja[key] != jb[key]:
                out.append(f"json {key}: {ja[key]!r} -> {jb[key]!r}")
    elif a.body != b.body:
        out.append(f"body changed ({len(a.body)} -> {len(b.body)} bytes)")
    return out


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
    original = send(req)
    oj = original.json()
    if not 200 <= original.status < 300 or not isinstance(oj, dict) or owner_field not in oj:
        raise ValueError(f"the original request did not return an owned object (status {original.status})")
    replayed = send(with_path_segment(req, own_id, other_id))
    rj = replayed.json()
    if 200 <= replayed.status < 300 and isinstance(rj, dict) and rj.get(owner_field) != oj[owner_field]:
        return Finding(f"IDOR: {other_id} readable by the owner of {own_id}", original, replayed,
                       diff(original, replayed))
    return None
