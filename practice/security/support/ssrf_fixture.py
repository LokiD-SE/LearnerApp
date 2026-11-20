"""Helpers for the SSRF and open redirect lesson (Track L, testing-ssrf-and-open-redirects).

``CallbackListener`` is a tiny HTTP server **you** run on ``127.0.0.1`` and hand to the target as a URL. It
records which paths were requested. If the target fetches a URL you gave it and you did not see the response,
a hit on the listener is the evidence - that is how blind SSRF is confirmed with a server you control.

It binds to loopback only and refuses anything else, like every practice target in this project.
"""

from __future__ import annotations

import contextlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator

import requests

LOOPBACK = ("127.0.0.1", "localhost", "::1")


class CallbackListener:
    """Records the path and User-Agent of every request it receives."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        if host not in LOOPBACK:
            raise ValueError("the callback listener only binds to the loopback interface")
        self.hits: list[tuple[str, str]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - http.server naming
                outer.hits.append((self.path, self.headers.get("User-Agent", "")))
                body = b"callback received"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: object) -> None:
                pass

        self._server = ThreadingHTTPServer((host, port), Handler)
        self._server.daemon_threads = True
        self.host, self.port = host, self._server.server_address[1]

    def url(self, token: str) -> str:
        """The URL to give the target; ``token`` makes this probe's hit recognisable."""
        return f"http://{self.host}:{self.port}/cb/{token}"

    def saw(self, token: str) -> bool:
        return any(path == f"/cb/{token}" for path, _ in self.hits)

    def start(self) -> "CallbackListener":
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


@contextlib.contextmanager
def listening() -> Iterator[CallbackListener]:
    listener = CallbackListener().start()
    try:
        yield listener
    finally:
        listener.stop()


def alice_token(base_url: str) -> str:
    """Signs in as the seeded merchant user and returns a bearer token for the practice portal."""
    r = requests.post(base_url + "/api/login",
                      json={"email": "alice@shop-a.example", "password": "alice-pass-1"}, timeout=5)
    return r.json()["token"]
