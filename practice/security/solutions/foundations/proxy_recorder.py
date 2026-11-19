"""A tiny recording forward proxy for HTTP (no TLS) - what ZAP and Burp do at their core, minus everything else.

Your browser or test client sends each request to the proxy in *absolute-form* (RFC 9112 section 3.2.2):
``GET http://127.0.0.1:8765/api/me HTTP/1.1``. The proxy parses the target, checks it is in scope, cleans the
hop-by-hop header fields (RFC 9110 section 7.6.1), adds its ``Via`` entry (section 7.6.3), forwards the request,
relays the response and records the pair as an ``Exchange`` in ``history``.

You write three functions; the server around them is given:

- ``parse_target(request_line)`` - split an absolute-form (or CONNECT authority-form) request line.
- ``in_scope(host, port, scope)`` - the scope check that stops you testing what you are not allowed to test.
- ``clean_headers(headers, target)`` - the header rules every intermediary must follow.

Practice safety: the proxy listens on loopback only and forwards only to loopback addresses, whatever the
scope says. It does not implement CONNECT (TLS tunnels), so it answers ``501`` to them.
"""

from __future__ import annotations

import contextlib
import http.client
import threading
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator

from proxy_fixture import Exchange

LOOPBACK = ("127.0.0.1", "localhost", "::1")
VIA_NAME = "sandpay-recorder"
# RFC 9110 section 7.6.1: fields an intermediary removes before forwarding, whether or not Connection names them.
HOP_BY_HOP = ("connection", "proxy-connection", "keep-alive", "te", "transfer-encoding", "upgrade")


class ProxyError(Exception):
    """A request the proxy refuses; ``status`` is what it answers with."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class Target:
    method: str
    scheme: str  # "http" for absolute-form; "" for CONNECT
    host: str  # lower-case
    port: int
    path: str  # path and query, at least "/"; "" for CONNECT
    version: str  # "HTTP/1.1"


def parse_target(request_line: str) -> Target:
    """Parse ``METHOD request-target HTTP-version`` as a proxy receives it.

    - absolute-form ``http://host[:port]/path?query`` -> scheme ``http``, port 80 if absent, path ``/`` if empty
      (fragments are never sent; ignore one if present);
    - ``CONNECT host:port`` (authority-form) -> method ``CONNECT``, scheme and path ``""``; the port is
      required (RFC 9110 section 9.3.6: "There is no default port");
    - anything else - origin-form (``/path``, sent to an origin server, not a proxy), a scheme other than
      ``http``, a missing host, a bad port or a malformed line - raises ``ProxyError(400, ...)``.
    The host is returned in lower case.
    """
    parts = request_line.strip().split(" ")
    if len(parts) != 3 or not parts[2].startswith("HTTP/"):
        raise ProxyError(400, f"malformed request line: {request_line!r}")
    method, target, version = parts
    if method == "CONNECT":
        host, sep, port_text = target.rpartition(":")
        if not sep or not host or not port_text.isdigit() or not 0 < int(port_text) < 65536:
            raise ProxyError(400, "CONNECT needs host:port")
        return Target("CONNECT", "", host.lower(), int(port_text), "", version)
    if target.startswith("/"):
        raise ProxyError(400, "origin-form request-target: a proxy needs the absolute URI")
    split = urllib.parse.urlsplit(target)
    if split.scheme.lower() != "http":
        raise ProxyError(400, f"unsupported scheme {split.scheme!r}")
    if not split.hostname:
        raise ProxyError(400, "missing host")
    try:
        port = split.port or 80
    except ValueError as exc:
        raise ProxyError(400, "bad port") from exc
    path = split.path or "/"
    if split.query:
        path += "?" + split.query
    return Target(method, "http", split.hostname.lower(), port, path, version)


def in_scope(host: str, port: int, scope: list[str]) -> bool:
    """True if ``host:port`` matches an entry of ``scope``.

    Entries are ``"host:port"`` or ``"host:*"`` (any port). Hosts compare case-insensitively and exactly -
    ``127.0.0.1`` does not match ``127.0.0.10``, and ``shop.example`` does not match ``evil-shop.example``.
    An empty scope matches nothing (ZAP: "By default nothing is in scope").
    """
    host = host.lower()
    for entry in scope:
        e_host, sep, e_port = entry.rpartition(":")
        if not sep:
            continue
        if e_host.lower() == host and (e_port == "*" or e_port == str(port)):
            return True
    return False


def clean_headers(headers: list[tuple[str, str]], target: Target) -> list[tuple[str, str]]:
    """The header fields to forward upstream, in their original order, with:

    - every field named in ``Connection`` removed, then ``Connection`` itself, and the fields in
      ``HOP_BY_HOP`` (RFC 9110 section 7.6.1) - names compare case-insensitively;
    - ``Host`` replaced by the target's host (with ``:port`` unless it is 80), at the position of the first
      received ``Host`` or appended if there was none (RFC 9112 section 3.2.2: the proxy "MUST generate a new
      Host field value based on the received request-target");
    - ``Via`` extended: append ``"1.1 sandpay-recorder"`` to an existing Via value (``", "`` between members)
      or add a new ``Via`` field at the end (RFC 9110 section 7.6.3).
    """
    named = set()
    for name, value in headers:
        if name.lower() == "connection":
            named.update(opt.strip().lower() for opt in value.split(",") if opt.strip())
    drop = named | set(HOP_BY_HOP)
    host_value = target.host if target.port == 80 else f"{target.host}:{target.port}"
    via_member = f"1.1 {VIA_NAME}"
    out: list[tuple[str, str]] = []
    host_done = via_done = False
    for name, value in headers:
        lower = name.lower()
        if lower in drop:
            continue
        if lower == "host":
            if not host_done:
                out.append(("Host", host_value))
                host_done = True
            continue
        if lower == "via" and not via_done:
            out.append((name, f"{value}, {via_member}"))
            via_done = True
            continue
        out.append((name, value))
    if not host_done:
        out.append(("Host", host_value))
    if not via_done:
        out.append(("Via", via_member))
    return out


# ---- the server (given) ----------------------------------------------------------------------------------
RESPONSE_SKIP = ("connection", "keep-alive", "transfer-encoding", "content-length", "proxy-connection")


class RecordingProxy(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, scope: list[str], port: int = 0):
        self.scope = scope
        self.history: list[Exchange] = []
        self.lock = threading.Lock()
        super().__init__(("127.0.0.1", port), _Handler)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    disable_nagle_algorithm = True
    server: RecordingProxy

    def _refuse(self, status: int, message: str) -> None:
        body = (message + "\n").encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def _proxy(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        try:
            target = parse_target(self.requestline)
        except ProxyError as e:
            return self._refuse(e.status, e.message)
        if target.method == "CONNECT":
            return self._refuse(501, "this practice proxy does not tunnel or intercept TLS")
        if target.host not in LOOPBACK:
            return self._refuse(403, f"{target.host} is not a loopback address - practice proxy refuses")
        if not in_scope(target.host, target.port, self.server.scope):
            return self._refuse(403, f"{target.host}:{target.port} is out of scope")
        headers = clean_headers(list(self.headers.items()), target)
        started = datetime.now(timezone.utc)
        t0 = time.perf_counter()
        conn = http.client.HTTPConnection(target.host, target.port, timeout=10)
        try:
            conn.putrequest(target.method, target.path, skip_host=True, skip_accept_encoding=True)
            for name, value in headers:
                conn.putheader(name, value)
            if body and not any(n.lower() == "content-length" for n, _ in headers):
                conn.putheader("Content-Length", str(len(body)))
            conn.endheaders(body or None)
            t1 = time.perf_counter()
            resp = conn.getresponse()
            t2 = time.perf_counter()
            resp_body = resp.read()
            t3 = time.perf_counter()
        except OSError as exc:
            conn.close()
            return self._refuse(502, f"upstream error: {exc}")
        conn.close()
        url = f"http://{target.host}:{target.port}{target.path}"
        exchange = Exchange(started, target.method, url, target.version, headers, body, resp.status, resp.reason,
                            list(resp.getheaders()), resp_body, (t1 - t0) * 1000, (t2 - t1) * 1000,
                            (t3 - t2) * 1000)
        with self.server.lock:
            self.server.history.append(exchange)
        self.send_response(resp.status, resp.reason)
        for name, value in resp.getheaders():
            if name.lower() not in RESPONSE_SKIP:
                self.send_header(name, value)
        self.send_header("Content-Length", str(len(resp_body)))
        self.end_headers()
        self.wfile.write(resp_body)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = do_CONNECT = _proxy

    def log_message(self, format: str, *args: object) -> None:
        pass


@contextlib.contextmanager
def run_proxy(scope: list[str]) -> Iterator[RecordingProxy]:
    """Start the recording proxy on a free loopback port; yields it (``.url``, ``.history``)."""
    proxy = RecordingProxy(scope)
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()
    try:
        yield proxy
    finally:
        proxy.shutdown()
        proxy.server_close()
