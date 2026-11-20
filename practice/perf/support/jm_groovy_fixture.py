"""A loopback-only SandPay API that wants signed payment requests - for the jm_groovy_ exercises.

Some payment APIs ask the client to sign every request so the server can tell that the body was not changed
on the way. No JMeter sampler can compute an HMAC, so a load test needs a script: this fixture is what makes
the JSR223 PreProcessor necessary. It is fictional (SandPay), synthetic and binds to 127.0.0.1 only.

| request            | behaviour                                                                            |
| ------------------ | ------------------------------------------------------------------------------------ |
| POST /auth/token   | ``{"access_token": "tok-<client_id>"}`` for ``merchant-<n>`` / ``secret-<n>``          |
| POST /v1/payments  | needs ``Authorization: Bearer tok-merchant-<n>``, ``Idempotency-Key``, ``X-Timestamp`` |
|                    | (Unix seconds, at most 300 s from the server clock) and ``X-Signature``:               |
|                    | lower-case hex HMAC-SHA256, key ``secret-<n>``, message                                |
|                    | ``<X-Timestamp>.<Idempotency-Key>.<raw body>``. A bad or missing signature is ``401``. |
|                    | A known key returns the stored response again (a replay, counted).                     |
|                    | Every 4th NEW payment (4, 8, 12 ...) is ``201`` with ``"status": "declined"``,          |
|                    | the rest ``201`` with ``"status": "captured"``.                                       |

The counter, not a random number, decides the declines, so 2 threads x 6 loops with unique keys give exactly
3 declined payments whatever the interleaving.

``serve()`` yields a ``Target`` with ``base_url``, ``port`` and ``stats()`` (created, replays, bad_signature,
keys seen).
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator

MAX_SKEW_S = 300


def signature(secret: str, timestamp: str, key: str, body: bytes) -> str:
    """The signature the server expects: hex HMAC-SHA256 of ``<timestamp>.<key>.<body>`` with the secret."""
    message = timestamp.encode() + b"." + key.encode() + b"." + body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


@dataclass
class _State:
    lock: threading.Lock = field(default_factory=threading.Lock)
    created: int = 0
    replays: int = 0
    bad_signature: int = 0
    stored: dict[str, tuple[int, dict]] = field(default_factory=dict)
    next_id: int = 7000


@dataclass
class Target:
    base_url: str
    port: int
    state: _State

    def stats(self) -> dict[str, Any]:
        with self.state.lock:
            return {"created": self.state.created, "replays": self.state.replays,
                    "bad_signature": self.state.bad_signature, "keys": sorted(self.state.stored)}


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
            if path != "/v1/payments":
                return self._reply(404, {"error": "not found"})
            auth = self.headers.get("Authorization", "")
            n = auth.removeprefix("Bearer tok-merchant-")
            if auth == n or not n.isdigit():
                return self._reply(401, {"error": "missing or unknown bearer token"})
            key = self.headers.get("Idempotency-Key", "")
            if not key:
                return self._reply(400, {"error": "Idempotency-Key header is required"})
            ts = self.headers.get("X-Timestamp", "")
            if not ts.isdigit() or abs(int(ts) - time.time()) > MAX_SKEW_S:
                with state.lock:
                    state.bad_signature += 1
                return self._reply(401, {"error": "X-Timestamp missing or outside 300 s"})
            expected = signature(f"secret-{n}", ts, key, body)
            if not hmac.compare_digest(expected, self.headers.get("X-Signature", "")):
                with state.lock:
                    state.bad_signature += 1
                return self._reply(401, {"error": "bad signature"})
            with state.lock:
                if key in state.stored:
                    state.replays += 1
                    status, stored = state.stored[key]
                    return self._reply(status, stored)
                state.created += 1
                state.next_id += 1
                status_text = "declined" if state.created % 4 == 0 else "captured"
                try:
                    amount = int(json.loads(body).get("amount_minor", 0))
                except (ValueError, AttributeError):
                    amount = 0
                payment = {"id": f"pay_{state.next_id}", "amount_minor": amount, "currency": "EUR",
                           "status": status_text}
                state.stored[key] = (201, payment)
            return self._reply(201, payment)

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
def serve() -> Iterator[Target]:
    state = _State()
    server = _Server(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        yield Target(f"http://127.0.0.1:{port}", port, state)
    finally:
        server.shutdown()
        server.server_close()
