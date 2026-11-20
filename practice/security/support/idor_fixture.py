"""A tiny SandPay invoices API for the access control lesson (Track L, testing-access-control-idor).

The practice portal answers "not yours" and "does not exist" the same way once ``idor`` is fixed, so it can
show only two of the four behaviours a tester meets. This server shows all four, chosen by ``mode``:

| mode            | another tenant's invoice          | an invoice that does not exist     |
| --------------- | --------------------------------- | ---------------------------------- |
| ``uniform``     | 404 ``invoice <id> not found``    | 404 ``invoice <id> not found``     |
| ``status``      | 403 ``forbidden``                 | 404 ``invoice <id> not found``     |
| ``message``     | 404 ``invoice <id> is not yours`` | 404 ``invoice <id> not found``     |
| ``leaky``       | 200 with the invoice              | 404 ``invoice <id> not found``     |

Only ``uniform`` gives no existence oracle; ``leaky`` is an IDOR. Loopback only; all data is synthetic.
Fixed tokens stand in for real sign-in: ``tok-shop-a`` (merchant m_100) and ``tok-shop-b`` (merchant m_200).
"""

from __future__ import annotations

import contextlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator

LOOPBACK = ("127.0.0.1", "localhost", "::1")
MODES = ("uniform", "status", "message", "leaky")
TOKENS = {"tok-shop-a": "m_100", "tok-shop-b": "m_200"}
INVOICES = {
    "inv_501": {"id": "inv_501", "merchant_id": "m_100", "amount_minor": 12000, "currency": "EUR"},
    "inv_502": {"id": "inv_502", "merchant_id": "m_100", "amount_minor": 450, "currency": "EUR"},
    "inv_601": {"id": "inv_601", "merchant_id": "m_200", "amount_minor": 9900, "currency": "GBP"},
}


def _handler_for(mode: str) -> type[BaseHTTPRequestHandler]:
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

        def do_GET(self) -> None:  # noqa: N802 - http.server naming
            auth = self.headers.get("Authorization", "")
            merchant = TOKENS.get(auth.removeprefix("Bearer ")) if auth.startswith("Bearer ") else None
            if merchant is None:
                return self._reply(401, {"error": "authentication required"})
            if not self.path.startswith("/invoices/"):
                return self._reply(404, {"error": "not found"})
            inv_id = self.path.rsplit("/", 1)[-1]
            inv = INVOICES.get(inv_id)
            if inv is None:
                return self._reply(404, {"error": f"invoice {inv_id} not found"})
            if inv["merchant_id"] == merchant or mode == "leaky":
                return self._reply(200, inv)
            if mode == "status":
                return self._reply(403, {"error": "forbidden"})
            if mode == "message":
                return self._reply(404, {"error": f"invoice {inv_id} is not yours"})
            return self._reply(404, {"error": f"invoice {inv_id} not found"})  # uniform

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return Handler


@contextlib.contextmanager
def serve_invoices(mode: str, host: str = "127.0.0.1") -> Iterator[str]:
    """Serves the invoices API in ``mode`` on loopback; yields the base URL."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if host not in LOOPBACK:
        raise ValueError("the practice server only binds to the loopback interface")
    server = ThreadingHTTPServer((host, 0), _handler_for(mode))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
