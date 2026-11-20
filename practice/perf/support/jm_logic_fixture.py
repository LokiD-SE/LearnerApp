"""A loopback-only SandPay API with deterministic failures - for the jm_logic_ exercises (logic controllers).

The shared practice target draws its injected errors at random, so the number of failed payments varies a
little between runs. Logic-controller exercises count samples exactly, so this server decides by a request
counter instead:

| request                      | behaviour                                                                     |
| ---------------------------- | ----------------------------------------------------------------------------- |
| POST /auth/token             | ``{"access_token": "tok-<client_id>"}`` for ``merchant-<n>`` / ``secret-<n>``  |
| POST /v1/payments            | needs ``Authorization: Bearer tok-...``; every 4th call (4, 8, 12 ...) is      |
|                              | ``500`` ``{"error": "acquirer timeout"}``; the rest are ``201`` with           |
|                              | ``{"id": "pay_<n>", "status": "captured"}``                                    |
| GET /v1/payments/<id>        | ``200`` for an id this server created, ``404`` otherwise                       |
| GET /v1/reports/settlement   | ``200`` ``{"report": "settlement"}``                                           |
| GET /metrics                 | ``{"routes": {"POST /auth/token": n, ...}, "statuses": {"201": n, ...}}``      |

Counters are shared by all threads, so the totals are exact whatever the interleaving: 24 calls to
``POST /v1/payments`` give 6 x 500 (calls 4, 8, ... 24) and 18 payments.

``serve()`` yields the base URL; the server binds to 127.0.0.1 only.
"""

from __future__ import annotations

import contextlib
import json
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator


class _State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.creates = 0
        self.next_id = 7000
        self.payments: set[str] = set()
        self.routes: Counter = Counter()
        self.statuses: Counter = Counter()


def _handle(state: _State, method: str, path: str, headers: dict[str, str], body: bytes) -> tuple[int, dict]:
    if path == "/metrics" and method == "GET":
        with state.lock:
            return 200, {"routes": dict(state.routes), "statuses": {str(k): v for k, v in state.statuses.items()}}
    if path == "/auth/token" and method == "POST":
        try:
            data = json.loads(body or b"{}")
        except json.JSONDecodeError:
            return 400, {"error": "body is not valid JSON"}
        cid, secret = str(data.get("client_id", "")), str(data.get("client_secret", ""))
        n = cid.removeprefix("merchant-")
        if not (n.isdigit() and 1 <= int(n) <= 50 and secret == f"secret-{n}"):
            return 401, {"error": "invalid client credentials"}
        return 200, {"access_token": f"tok-{cid}", "token_type": "Bearer", "expires_in": 3600}
    if not headers.get("authorization", "").startswith("Bearer tok-merchant-"):
        return 401, {"error": "missing or unknown bearer token"}
    if path == "/v1/payments" and method == "POST":
        with state.lock:
            state.creates += 1
            if state.creates % 4 == 0:
                return 500, {"error": "acquirer timeout"}
            state.next_id += 1
            pid = f"pay_{state.next_id}"
            state.payments.add(pid)
        return 201, {"id": pid, "status": "captured"}
    if path.startswith("/v1/payments/") and method == "GET":
        with state.lock:
            known = path.rsplit("/", 1)[-1] in state.payments
        return (200, {"id": path.rsplit("/", 1)[-1], "status": "captured"}) if known else (
            404, {"error": "payment not found"})
    if path == "/v1/reports/settlement" and method == "GET":
        return 200, {"report": "settlement", "rows": 42}
    return 404, {"error": "not found"}


def _route_name(method: str, path: str) -> str:
    return f"{method} /v1/payments/<id>" if path.startswith("/v1/payments/") else f"{method} {path}"


def _handler_for(state: _State) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _serve(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            path = self.path.split("?", 1)[0]
            headers = {k.lower(): v for k, v in self.headers.items()}
            status, payload = _handle(state, self.command, path, headers, body)
            if path != "/metrics":
                with state.lock:
                    state.routes[_route_name(self.command, path)] += 1
                    state.statuses[status] += 1
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = _serve

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return Handler


@contextlib.contextmanager
def serve() -> Iterator[str]:
    """Run the fixture on 127.0.0.1 and a free port; yields ``http://127.0.0.1:<port>``."""
    state = _State()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_for(state))
    server.daemon_threads = True
    # Nagle off, as in the shared targets: no 40 ms keep-alive floor on small responses.
    import socket

    server.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def metrics(base_url: str) -> dict:
    """The fixture's own counts - the system's view, to compare with what JMeter recorded."""
    import urllib.request

    with urllib.request.urlopen(f"{base_url}/metrics", timeout=5) as resp:
        return json.loads(resp.read())
