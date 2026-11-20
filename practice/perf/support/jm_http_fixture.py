"""A small loopback-only HTTP server for the "HTTP samplers and configuration" lesson (Track K).

It records, for every request, which TCP connection carried it (the client's address and port), so tests and the
lesson can SEE connection reuse - keep-alive on or off, connections reset between iterations - from the server's
side, instead of guessing from timings. It also has the endpoints the lesson's demos need:

| method | path              | behaviour                                                                     |
| ------ | ----------------- | ----------------------------------------------------------------------------- |
| GET    | /conn             | ``200 {"ok": true}``                                                          |
| POST   | /login            | sets cookie ``sid``; ``200``                                                  |
| GET    | /account          | ``200`` with a valid ``sid`` cookie, else ``401``                             |
| GET    | /rates            | ``200`` with ``ETag``, ``Last-Modified`` and ``Cache-Control: max-age=60``;   |
|        |                   | ``304`` when ``If-None-Match`` matches                                        |
| GET    | /old-path         | ``302`` to ``/conn``                                                          |
| GET    | /slow?ms=500      | answers after ``ms`` milliseconds (timeouts demo)                             |
| GET    | /echo-headers     | ``200`` with the request headers as JSON (what did JMeter really send?)       |

``with serve_recording() as (base_url, log): ...`` - ``log`` is a list of ``Hit(connection, method, path,
headers)`` appended in arrival order. SandPay is fictional; nothing leaves the machine.
"""

from __future__ import annotations

import contextlib
import json
import secrets
import threading
import time
import urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator

ETAG = '"rates-v7"'
LAST_MODIFIED = "Wed, 18 Nov 2026 09:00:00 GMT"


@dataclass(frozen=True)
class Hit:
    connection: str  # "127.0.0.1:54012" - the client end of the TCP connection that carried the request
    method: str
    path: str
    headers: dict[str, str]


def _handler(log: list[Hit], lock: threading.Lock, sessions: set[str]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        disable_nagle_algorithm = True

        def _send(self, status: int, body: dict | None = None, headers: list[tuple[str, str]] | None = None) -> None:
            data = json.dumps(body).encode() if body is not None else b""
            self.send_response(status)
            if body is not None:
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            for k, v in headers or []:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def _serve(self) -> None:
            split = urllib.parse.urlsplit(self.path)
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            headers = {k: v for k, v in self.headers.items()}
            with lock:
                log.append(Hit(f"{self.client_address[0]}:{self.client_address[1]}", self.command, split.path,
                               headers))
            cookies = dict(c.strip().split("=", 1) for c in self.headers.get("Cookie", "").split(";") if "=" in c)
            if split.path == "/conn":
                self._send(200, {"ok": True})
            elif split.path == "/login" and self.command == "POST":
                sid = secrets.token_hex(8)
                with lock:
                    sessions.add(sid)
                self._send(200, {"signed_in": True}, [("Set-Cookie", f"sid={sid}; Path=/; HttpOnly")])
            elif split.path == "/account":
                if cookies.get("sid") in sessions:
                    self._send(200, {"merchant": "merchant-7"})
                else:
                    self._send(401, {"error": "sign in first"})
            elif split.path == "/rates":
                if self.headers.get("If-None-Match") == ETAG:
                    self._send(304, None, [("ETag", ETAG)])
                else:
                    self._send(200, {"EUR_GBP": "0.87"}, [("ETag", ETAG), ("Last-Modified", LAST_MODIFIED),
                                                          ("Cache-Control", "max-age=60")])
            elif split.path == "/old-path":
                self._send(302, None, [("Location", "/conn")])
            elif split.path == "/slow":
                ms = float(urllib.parse.parse_qs(split.query).get("ms", ["500"])[0])
                time.sleep(ms / 1000)
                self._send(200, {"slept_ms": ms})
            elif split.path == "/echo-headers":
                self._send(200, headers)
            else:
                self._send(404, {"error": "not found"})

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _serve

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return Handler


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request: Any, client_address: Any) -> None:
        import sys

        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)


@contextlib.contextmanager
def serve_recording(host: str = "127.0.0.1") -> Iterator[tuple[str, list[Hit]]]:
    """Serves on loopback in a background thread; yields ``(base_url, log)``."""
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("the practice server only binds to the loopback interface")
    log: list[Hit] = []
    server = _Server((host, 0), _handler(log, threading.Lock(), set()))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{server.server_address[1]}", log
    finally:
        server.shutdown()
        server.server_close()
