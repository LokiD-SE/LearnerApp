"""Login servers that differ in exactly ONE user-enumeration signal - for the testing-authentication lesson.

Loopback only, like every practice target. SandPay and its accounts are fictional.

``serve_login(variant)`` yields a base URL with ``POST /login`` taking ``{"email", "password"}``:

| variant   | unknown email vs known email with a wrong password                                        |
| --------- | ----------------------------------------------------------------------------------------- |
| uniform   | same status (401), same body, same work (a dummy hash for unknown users) - nothing leaks   |
| message   | same status and work, different error text ("no account" vs "wrong password")              |
| status    | same body and work, different status (404 vs 401)                                         |
| timing    | same status and body, but the slow hash runs only for known users (the "quick exit")      |

The "slow hash" is a fixed 60 ms sleep so the timing gap is the same on every machine; a real password hash
(PBKDF2, bcrypt, Argon2) behaves the same way, as the SandPay portal shows once its ``weak-hash`` flaw is fixed.
"""

from __future__ import annotations

import contextlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator

VARIANTS = ("uniform", "message", "status", "timing")
USERS = {"alice@shop-a.example": "alice-pass-1", "bob@shop-b.example": "bob-pass-2"}
HASH_SECONDS = 0.06


def _slow_hash() -> None:
    time.sleep(HASH_SECONDS)


def _login(variant: str, email: str, password: str) -> tuple[int, dict]:
    known = email in USERS
    if variant == "timing":
        if not known:
            return 401, {"error": "invalid email or password"}  # quick exit: no hash for unknown users
        _slow_hash()
        ok = USERS[email] == password
        return (200, {"status": "signed in"}) if ok else (401, {"error": "invalid email or password"})
    _slow_hash()  # every other variant does the same work for known and unknown users
    if known and USERS[email] == password:
        return 200, {"status": "signed in"}
    if variant == "message":
        return 401, {"error": "wrong password" if known else "no account with that email"}
    if variant == "status":
        return (401 if known else 404), {"error": "invalid email or password"}
    return 401, {"error": "invalid email or password"}


@contextlib.contextmanager
def serve_login(variant: str) -> Iterator[str]:
    if variant not in VARIANTS:
        raise ValueError(f"variant must be one of {VARIANTS}")

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        disable_nagle_algorithm = True

        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            try:
                data = json.loads(body or b"{}")
            except json.JSONDecodeError:
                data = {}
            if self.path != "/login":
                status, payload = 404, {"error": "not found"}
            else:
                status, payload = _login(variant, str(data.get("email", "")), str(data.get("password", "")))
            out = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
