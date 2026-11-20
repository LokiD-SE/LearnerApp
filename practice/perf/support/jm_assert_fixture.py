"""A loopback-only SandPay API whose failures are deterministic - for the jm_assert_ exercises.

The shared practice target draws its injected errors at random, so the number of failures varies a little
between runs. Assertion exercises need exact counts, so this server decides by a request counter instead:

| request                      | behaviour                                                                    |
| ---------------------------- | ---------------------------------------------------------------------------- |
| POST /auth/token             | ``{"access_token": "tok-<client_id>"}`` for ``merchant-<n>`` / ``secret-<n>`` |
| GET /v1/payments             | every 4th call (4, 8, 12 ...) is a *soft error*: ``200`` with                 |
|                              | ``{"error": "ledger read timeout"}`` and no ``data`` - looks fine by status  |
| POST /v1/payments            | every 5th call (5, 10, 15 ...) is ``500`` ``{"error": "acquirer timeout"}``; |
|                              | every 7th call that is not a 5th is ``201`` with ``"status": "declined"``;    |
|                              | the rest are ``201`` with ``"status": "captured"``                            |
| GET /v1/reports/settlement   | always correct, always slow: 150 ms                                          |

Counters are shared by all threads, so the totals are exact whatever the interleaving: 20 calls to
``POST /v1/payments`` give 4 x 500 (calls 5, 10, 15, 20) and 2 x declined (calls 7, 14).

``serve()`` yields the base URL; the server binds to 127.0.0.1 only.
"""

from __future__ import annotations

import contextlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator

REPORT_DELAY_S = 0.150


class _State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.lists = 0
        self.creates = 0
        self.next_id = 5000

    def next_list(self) -> int:
        with self.lock:
            self.lists += 1
            return self.lists

    def next_create(self) -> tuple[int, int]:
        with self.lock:
            self.creates += 1
            self.next_id += 1
            return self.creates, self.next_id


def _handler(state: _State) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        disable_nagle_algorithm = True

        def _reply(self, status: int, body: dict) -> None:
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorised(self) -> bool:
            if self.headers.get("Authorization", "").startswith("Bearer tok-merchant-"):
                return True
            self._reply(401, {"error": "missing or unknown bearer token"})
            return False

        def do_POST(self) -> None:  # noqa: N802 - http.server naming
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            path = self.path.split("?", 1)[0]
            if path == "/auth/token":
                try:
                    data = json.loads(body or b"{}")
                except json.JSONDecodeError:
                    return self._reply(400, {"error": "body is not valid JSON"})
                cid = str(data.get("client_id", ""))
                n = cid.removeprefix("merchant-")
                if n.isdigit() and data.get("client_secret") == f"secret-{n}":
                    return self._reply(200, {"access_token": f"tok-{cid}", "token_type": "Bearer"})
                return self._reply(401, {"error": "invalid client credentials"})
            if path == "/v1/payments":
                if not self._authorised():
                    return None
                call, pid = state.next_create()
                if call % 5 == 0:
                    return self._reply(500, {"error": "acquirer timeout"})
                status = "declined" if call % 7 == 0 else "captured"
                return self._reply(201, {"id": f"pay_{pid}", "amount_minor": 1250, "currency": "EUR", "status": status})
            return self._reply(404, {"error": "not found"})

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path == "/health":
                return self._reply(200, {"status": "ok"})
            if not self._authorised():
                return None
            if path == "/v1/payments":
                if state.next_list() % 4 == 0:
                    return self._reply(200, {"error": "ledger read timeout"})
                return self._reply(200, {"data": [{"id": "pay_4001", "status": "captured"}], "has_more": False})
            if path == "/v1/reports/settlement":
                time.sleep(REPORT_DELAY_S)
                return self._reply(200, {"report": "settlement", "rows": 42})
            return self._reply(404, {"error": "not found"})

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
def serve() -> Iterator[str]:
    server = _Server(("127.0.0.1", 0), _handler(_State()))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
