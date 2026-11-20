"""SandPay sign-in service - a DELIBERATELY VULNERABLE session-management target for the lesson
"Testing session management" (Track L). Loopback only; never deploy or expose it. All data is synthetic.

The shared portal (``sandpay_vuln.py``) has no pre-login session, no logout and no timeouts, so this small
service adds exactly those behaviours. Each session flaw has an id; ``make_app(fixed={...})`` closes them:

| flaw id               | what is wrong                                                            | WSTG        |
| --------------------- | ------------------------------------------------------------------------ | ----------- |
| ``fixation``          | the pre-login session id is kept at login (not rotated)                   | WSTG-SESS-03 |
| ``url-session``       | the session id is also accepted from ``?sid=`` and written into links     | WSTG-SESS-04 |
| ``logout-client-only``| logout clears the cookie but leaves the server-side session valid         | WSTG-SESS-06 |
| ``no-idle-timeout``   | an idle session never expires                                             | WSTG-SESS-07 |
| ``no-absolute-timeout``| an active session lives for ever                                         | WSTG-SESS-07 |
| ``predictable-ids``   | ids come from a counter (``s0003e9``) instead of a CSPRNG                 | WSTG-SESS-01 |

Fixed values: idle timeout ``IDLE_TIMEOUT_S`` (10 minutes) and absolute timeout ``ABSOLUTE_TIMEOUT_S``
(4 hours) - inside the ranges the OWASP Session Management Cheat Sheet gives as common. Random ids are
``secrets.token_urlsafe(16)`` (128 bits, as ASVS 5.0.0 7.2.3 requires for reference tokens).

Time is injectable so tests never sleep: ``app.clock`` is a ``FakeClock`` and ``app.clock.advance(s)`` moves it.

Endpoints:

| method | path       | notes                                                                                   |
| ------ | ---------- | --------------------------------------------------------------------------------------- |
| GET    | /login     | sign-in page; starts an anonymous session (``Set-Cookie: sid=...``) if none is presented |
| POST   | /login     | form or JSON ``email``, ``password``; 200 + the authenticated session, or 401            |
| GET    | /account   | 200 with the signed-in email, or 401 ``{"error": "session invalid or expired"}``        |
| POST   | /logout    | ends the session and expires the cookie                                                 |

Run by hand: ``.venv/bin/python support/sess_fixture.py --port 8766 [--fix fixation ...]``
Seeded users (synthetic): ``alice@shop-a.example`` / ``alice-pass-1``, ``bob@shop-b.example`` / ``bob-pass-2``.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import secrets
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator

FLAWS = ("fixation", "url-session", "logout-client-only", "no-idle-timeout", "no-absolute-timeout", "predictable-ids")
LOOPBACK = ("127.0.0.1", "localhost", "::1")
IDLE_TIMEOUT_S = 600
ABSOLUTE_TIMEOUT_S = 4 * 3600
USERS = {"alice@shop-a.example": "alice-pass-1", "bob@shop-b.example": "bob-pass-2"}


class FakeClock:
    """Seconds since start; only moves when ``advance`` is called (or ``real=True`` follows the wall clock)."""

    def __init__(self) -> None:
        self._now = 0.0
        self._lock = threading.Lock()

    def __call__(self) -> float:
        with self._lock:
            return self._now

    def advance(self, seconds: float) -> None:
        with self._lock:
            self._now += seconds


@dataclass
class Session:
    sid: str
    created: float
    last_seen: float
    email: str | None = None  # None = anonymous (pre-login)
    authenticated_at: float | None = None


@dataclass
class SessionApp:
    fixed: frozenset[str]
    clock: Any = field(default_factory=FakeClock)
    sessions: dict[str, Session] = field(default_factory=dict)
    counter: int = 1000
    lock: threading.Lock = field(default_factory=threading.Lock)

    def is_fixed(self, flaw: str) -> bool:
        return flaw in self.fixed

    def new_id(self) -> str:
        with self.lock:
            self.counter += 1
            if self.is_fixed("predictable-ids"):
                return secrets.token_urlsafe(16)
            return f"s{self.counter:06x}"  # FLAW predictable-ids

    def start(self, email: str | None = None) -> Session:
        now = self.clock()
        s = Session(self.new_id(), now, now, email, now if email else None)
        self.sessions[s.sid] = s
        return s

    def lookup(self, sid: str | None) -> Session | None:
        """The live session for ``sid``, applying the timeouts; expired sessions are destroyed."""
        if not sid:
            return None
        s = self.sessions.get(sid)
        if s is None:
            return None
        now = self.clock()
        idle_expired = self.is_fixed("no-idle-timeout") and now - s.last_seen > IDLE_TIMEOUT_S
        start = s.authenticated_at if s.authenticated_at is not None else s.created
        absolute_expired = self.is_fixed("no-absolute-timeout") and now - start > ABSOLUTE_TIMEOUT_S
        if idle_expired or absolute_expired:
            del self.sessions[sid]
            return None
        s.last_seen = now
        return s


def make_app(fixed: set[str] | frozenset[str] | tuple[str, ...] = ()) -> SessionApp:
    """The vulnerable sign-in service; ``fixed`` names the flaws to fix. ``make_app(FLAWS)`` fixes all six."""
    unknown = set(fixed) - set(FLAWS)
    if unknown:
        raise ValueError(f"unknown flaw ids: {sorted(unknown)}; known: {FLAWS}")
    return SessionApp(frozenset(fixed))


def _cookie(sid: str) -> str:
    return f"sid={sid}; Path=/; HttpOnly; SameSite=Lax"


def _handler_for(app: SessionApp) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        disable_nagle_algorithm = True

        def _send(self, status: int, body: dict | str, headers: list[tuple[str, str]] | None = None) -> None:
            data = (json.dumps(body) if isinstance(body, dict) else body).encode()
            self.send_response(status)
            ctype = "application/json" if isinstance(body, dict) else "text/html; charset=utf-8"
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            for k, v in headers or []:
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _sid(self, query: dict[str, str]) -> str | None:
            cookies = {k: m.value for k, m in SimpleCookie(self.headers.get("Cookie", "")).items()}
            if cookies.get("sid"):
                return cookies["sid"]
            if not app.is_fixed("url-session"):
                return query.get("sid")  # FLAW url-session: the id is accepted from the URL
            return None

        def _serve(self) -> None:
            split = urllib.parse.urlsplit(self.path)
            query = {k: v[0] for k, v in urllib.parse.parse_qs(split.query).items()}
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            path, method = split.path, self.command
            if path == "/login" and method == "GET":
                s = app.lookup(self._sid(query))
                headers = []
                if s is None:
                    s = app.start()
                    headers.append(("Set-Cookie", _cookie(s.sid)))
                link = "/account" if app.is_fixed("url-session") else f"/account?sid={s.sid}"
                page = ("<!doctype html><title>SandPay sign-in</title><form method=post action=/login>"
                        f'<input name=email><input name=password type=password><button>Sign in</button></form>'
                        f'<a href="{link}">Your account</a>')
                return self._send(200, page, headers)
            if path == "/login" and method == "POST":
                ctype = self.headers.get("Content-Type", "")
                try:
                    data = (json.loads(body or b"{}") if "json" in ctype
                            else {k: v[0] for k, v in urllib.parse.parse_qs(body.decode()).items()})
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return self._send(400, {"error": "bad request body"})
                email, password = str(data.get("email", "")), str(data.get("password", ""))
                if USERS.get(email) != password:
                    return self._send(401, {"error": "invalid email or password"})
                current = app.lookup(self._sid(query))
                if current is not None and not app.is_fixed("fixation"):
                    # FLAW fixation: the anonymous session is promoted in place - same id before and after
                    now = app.clock()
                    current.email, current.authenticated_at = email, now
                    return self._send(200, {"email": email}, [("Set-Cookie", _cookie(current.sid))])
                if current is not None:
                    app.sessions.pop(current.sid, None)  # fixed: destroy the pre-login session ...
                s = app.start(email)  # ... and issue a fresh id
                return self._send(200, {"email": email}, [("Set-Cookie", _cookie(s.sid))])
            if path == "/account" and method == "GET":
                s = app.lookup(self._sid(query))
                if s is None or s.email is None:
                    return self._send(401, {"error": "session invalid or expired"})
                return self._send(200, {"email": s.email})
            if path == "/logout" and method == "POST":
                sid = self._sid(query)
                if sid and app.is_fixed("logout-client-only"):
                    app.sessions.pop(sid, None)  # fixed: the server forgets the session
                # FLAW logout-client-only when not fixed: only the browser is told to drop the cookie
                return self._send(200, {"status": "signed out"}, [("Set-Cookie", "sid=; Path=/; Max-Age=0")])
            return self._send(404, {"error": "not found"})

        do_GET = do_POST = _serve

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return Handler


@contextlib.contextmanager
def serve(app: SessionApp, host: str = "127.0.0.1", port: int = 0) -> Iterator[str]:
    """Serves ``app`` on loopback in a background thread; yields the base URL."""
    if host not in LOOPBACK:
        raise ValueError("the vulnerable practice service only binds to the loopback interface")
    server = ThreadingHTTPServer((host, port), _handler_for(app))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="SandPay deliberately vulnerable sign-in service (loopback only)")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--fix", action="append", default=[], choices=FLAWS)
    parser.add_argument("--fix-all", action="store_true")
    args = parser.parse_args()
    app = make_app(FLAWS if args.fix_all else args.fix)
    app.clock = time.monotonic  # by hand: real time
    with serve(app, port=args.port) as url:
        print(f"SandPay sign-in service on {url} (fixed: {sorted(app.fixed) or 'none'}) - Ctrl+C to stop", flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
