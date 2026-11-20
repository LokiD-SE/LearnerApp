"""A loopback-only SandPay *legacy acquirer gateway* - the target for the lc_valid_ Locust exercises.

Some older payment gateways answer every charge with HTTP ``200`` and put the real outcome in the body. A load
test that only looks at status codes reports 0% errors against them. This server behaves like that, and it
decides by a request counter (not a random number), so the totals are exact:

| request                          | behaviour                                                                 |
| -------------------------------- | ------------------------------------------------------------------------- |
| POST /gateway/login              | JSON ``{"username": "merchant-<n>", "password": "secret-<n>"}`` (n 1-50);  |
|                                  | ``200`` and a ``gw_session`` cookie, or ``401``                            |
| POST /gateway/charges            | needs the cookie (else ``401``). Charge call number c:                     |
|                                  | c divisible by 7 -> ``200`` with an HTML error page (not JSON);           |
|                                  | else c divisible by 4 -> ``200`` ``{"status": "declined",                  |
|                                  | "decline_code": "insufficient_funds"}``; else ``200`` ``"approved"``       |
| POST /gateway/charges/<id>/void  | ``200`` ``{"status": "voided"}``; the charge is then gone                  |
| GET /gateway/charges/<id>        | ``200`` with the charge, or ``404`` (unknown or voided)                    |
| GET /gateway/metrics             | the counters below (not counted themselves)                               |

``metrics()`` keys: ``logins``, ``charges``, ``html_errors``, ``declined``, ``approved``, ``voids``,
``lookups_found``, ``lookups_missing``, ``unauthenticated``.

``serve()`` yields the base URL; the server binds to 127.0.0.1 only. All data is synthetic.
"""

from __future__ import annotations

import contextlib
import json
import secrets
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator

HTML_ERROR = b"<html><body><h1>502 Bad Gateway</h1><p>upstream acquirer timeout</p></body></html>"


class _State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.counts: Counter = Counter()
        self.sessions: dict[str, str] = {}
        self.charges: dict[str, dict] = {}
        self.next_id = 7000

    def bump(self, key: str) -> int:
        with self.lock:
            self.counts[key] += 1
            return self.counts[key]


def _handler(state: _State) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        disable_nagle_algorithm = True

        def _send(self, status: int, data: bytes, ctype: str, headers: list[tuple[str, str]] | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            for k, v in headers or []:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def _json(self, status: int, body: dict, headers: list[tuple[str, str]] | None = None) -> None:
            self._send(status, json.dumps(body).encode(), "application/json", headers)

        def _merchant(self) -> str | None:
            for part in self.headers.get("Cookie", "").split(";"):
                name, _, value = part.strip().partition("=")
                if name == "gw_session":
                    with state.lock:
                        return state.sessions.get(value)
            return None

        def do_GET(self) -> None:  # noqa: N802 (http.server naming)
            if self.path == "/gateway/metrics":
                with state.lock:
                    keys = ("logins", "charges", "html_errors", "declined", "approved", "voids",
                            "lookups_found", "lookups_missing", "unauthenticated")
                    return self._json(200, {k: state.counts[k] for k in keys})
            if self.path.startswith("/gateway/charges/"):
                if self._merchant() is None:
                    state.bump("unauthenticated")
                    return self._json(401, {"error": "login required"})
                cid = self.path.rsplit("/", 1)[-1]
                with state.lock:
                    charge = state.charges.get(cid)
                if charge is None:
                    state.bump("lookups_missing")
                    return self._json(404, {"error": "charge not found"})
                state.bump("lookups_found")
                return self._json(200, charge)
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                return self._json(400, {"error": "body is not valid JSON"})
            if self.path == "/gateway/login":
                user, pw = str(data.get("username", "")), str(data.get("password", ""))
                n = user.removeprefix("merchant-")
                if not (n.isdigit() and 1 <= int(n) <= 50 and pw == f"secret-{n}"):
                    return self._json(401, {"error": "invalid credentials"})
                token = secrets.token_urlsafe(12)
                with state.lock:
                    state.sessions[token] = user
                state.bump("logins")
                return self._json(200, {"merchant": user}, [("Set-Cookie", f"gw_session={token}; Path=/; HttpOnly")])
            merchant = self._merchant()
            if merchant is None:
                state.bump("unauthenticated")
                return self._json(401, {"error": "login required"})
            if self.path == "/gateway/charges":
                c = state.bump("charges")
                if c % 7 == 0:
                    state.bump("html_errors")
                    return self._send(200, HTML_ERROR, "text/html")
                with state.lock:
                    state.next_id += 1
                    cid = f"ch_{state.next_id}"
                if c % 4 == 0:
                    state.bump("declined")
                    return self._json(200, {"id": cid, "status": "declined", "decline_code": "insufficient_funds"})
                charge = {"id": cid, "merchant": merchant, "amount_minor": data.get("amount_minor"),
                          "currency": data.get("currency"), "status": "approved"}
                with state.lock:
                    state.charges[cid] = charge
                state.bump("approved")
                return self._json(200, charge)
            if self.path.startswith("/gateway/charges/") and self.path.endswith("/void"):
                cid = self.path.split("/")[3]
                with state.lock:
                    found = state.charges.pop(cid, None)
                if found is None:
                    return self._json(404, {"error": "charge not found"})
                state.bump("voids")
                return self._json(200, {"id": cid, "status": "voided"})
            self._json(404, {"error": "not found"})

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return Handler


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 256

    def handle_error(self, request: Any, client_address: Any) -> None:
        import sys
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)


@contextlib.contextmanager
def serve(host: str = "127.0.0.1", port: int = 0) -> Iterator[str]:
    """Serves the gateway on loopback in a background thread; yields the base URL."""
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("the practice gateway only binds to the loopback interface")
    server = _Server((host, port), _handler(_State()))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def metrics(base_url: str) -> dict[str, int]:
    """The gateway's counters (standard library only, so tests can call it without requests)."""
    import urllib.request

    with urllib.request.urlopen(f"{base_url}/gateway/metrics", timeout=5) as r:
        return json.loads(r.read())


if __name__ == "__main__":
    import argparse
    import time

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8091)
    args = parser.parse_args()
    with serve(port=args.port) as url:
        print(f"SandPay legacy gateway on {url} (Ctrl+C to stop)")
        with contextlib.suppress(KeyboardInterrupt):
            while True:
                time.sleep(3600)
