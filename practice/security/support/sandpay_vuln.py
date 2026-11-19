"""SandPay Merchant Portal - a DELIBERATELY VULNERABLE practice app for the security testing track (Track L).

Never deploy it, never expose it: it binds to the loopback interface only and refuses any other address.
SandPay is fictional; every merchant, payment, password and secret here is synthetic.

Each flaw has an id. ``make_app(fixed={...})`` builds the same app with those flaws fixed, so an exercise can
prove both that a test finds the flaw and that it stays quiet once the flaw is fixed (no false positive).

| flaw id            | where                                   | OWASP Top 10:2021 / API Top 10:2023      |
| ------------------ | --------------------------------------- | ---------------------------------------- |
| ``idor``           | GET /api/payments/<id>                  | A01 Broken Access Control / API1 BOLA    |
| ``mass-assignment``| PATCH /api/profile (accepts ``role``)   | A01 / API3 Broken Object Property Level  |
| ``sqli``           | GET /api/payments?status=...            | A03 Injection                            |
| ``xss-reflected``  | GET /search?q=...                       | A03 Injection (XSS)                      |
| ``xss-stored``     | POST /api/notes then GET /notes         | A03 Injection (XSS)                      |
| ``path-traversal`` | GET /files?name=...                     | A01 Broken Access Control                |
| ``open-redirect``  | GET /login?next=...                     | A01 (unvalidated redirect)               |
| ``ssrf``           | POST /api/webhooks/test {"url": ...}    | A10 SSRF / API7                          |
| ``csrf``           | POST /settings/email (form)             | A01 (cross-site request forgery)         |
| ``weak-session``   | Set-Cookie on login                     | A07 Identification and Auth Failures     |
| ``no-rate-limit``  | POST /api/login                         | A07 / API4 Unrestricted Resource Use     |
| ``jwt-none``       | Authorization: Bearer <JWT>             | A07 / A02 Cryptographic Failures         |
| ``weak-hash``      | stored password hashes (unsalted MD5)   | A02 Cryptographic Failures               |
| ``verbose-errors`` | any unhandled error returns a traceback | A05 Security Misconfiguration            |
| ``missing-headers``| no CSP, X-Content-Type-Options, ...     | A05 Security Misconfiguration            |
| ``data-exposure``  | GET /api/merchants/<id> returns secrets | A01 / API3 Excessive Data Exposure       |
| ``secret-logging`` | passwords written to the access log     | A09 Security Logging and Monitoring      |

Run it by hand:  ``.venv/bin/python support/sandpay_vuln.py --port 8765 [--fix idor --fix sqli ...]``
In tests:        ``with serve(make_app()) as base_url: ...``

Seeded users (synthetic): ``alice@shop-a.example`` / ``alice-pass-1`` (merchant m_100, role merchant),
``bob@shop-b.example`` / ``bob-pass-2`` (merchant m_200, role merchant), ``ops@sandpay.example`` /
``ops-pass-3`` (role admin).
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import hmac
import html
import ipaddress
import json
import secrets
import sqlite3
import threading
import time
import traceback
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Iterator

FLAWS = (
    "idor", "mass-assignment", "sqli", "xss-reflected", "xss-stored", "path-traversal", "open-redirect",
    "ssrf", "csrf", "weak-session", "no-rate-limit", "jwt-none", "weak-hash", "verbose-errors",
    "missing-headers", "data-exposure", "secret-logging",
)
LOOPBACK = ("127.0.0.1", "localhost", "::1")
JWT_SECRET = b"sandpay-practice-only-jwt-key"  # synthetic; the fixed app verifies HS256 with it
FILES = {"terms.txt": "SandPay merchant terms (practice copy).\n", "fees.txt": "Card fee: 1.4% + 0.25 EUR\n"}
SECRET_FILE = "internal/settlement-keys.txt"  # what path traversal can reach
SECRET_FILE_BODY = "SETTLEMENT_SIGNING_KEY=sk_practice_do_not_use\n"
LOGIN_LIMIT = 5  # attempts per account per window when no-rate-limit is fixed
LOGIN_WINDOW_S = 60.0


class HttpError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class Response:
    status: int = 200
    body: bytes = b""
    headers: list[tuple[str, str]] = field(default_factory=list)

    @staticmethod
    def json(data: Any, status: int = 200) -> "Response":
        return Response(status, json.dumps(data).encode(), [("Content-Type", "application/json")])

    @staticmethod
    def html(text: str, status: int = 200) -> "Response":
        return Response(status, text.encode(), [("Content-Type", "text/html; charset=utf-8")])


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, str]
    headers: dict[str, str]  # lower-case names
    body: bytes
    cookies: dict[str, str]

    def json(self) -> dict:
        try:
            data = json.loads(self.body or b"{}")
        except json.JSONDecodeError as exc:
            raise HttpError(400, "body is not valid JSON") from exc
        if not isinstance(data, dict):
            raise HttpError(400, "body must be a JSON object")
        return data

    def form(self) -> dict[str, str]:
        return {k: v[0] for k, v in urllib.parse.parse_qs(self.body.decode()).items()}


def _md5(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()


def _pbkdf2(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"


def _pbkdf2_check(password: str, stored: str) -> bool:
    _, iterations, salt_hex, digest_hex = stored.split("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
    return hmac.compare_digest(digest.hex(), digest_hex)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_jwt(claims: dict, alg: str = "HS256", key: bytes = JWT_SECRET) -> str:
    """Encodes a JWT (RFC 7519) - used by the app and by tests that need a valid token."""
    header = _b64url(json.dumps({"alg": alg, "typ": "JWT"}).encode())
    payload = _b64url(json.dumps(claims).encode())
    if alg == "none":
        return f"{header}.{payload}."
    sig = hmac.new(key, f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64url(sig)}"


class App:
    """The portal. Not thread-safe by design beyond a lock around the database (enough for practice)."""

    def __init__(self, fixed: frozenset[str]):
        unknown = set(fixed) - set(FLAWS)
        if unknown:
            raise ValueError(f"unknown flaw ids: {sorted(unknown)}; known: {FLAWS}")
        self.fixed = fixed
        self.lock = threading.Lock()
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.sessions: dict[str, dict] = {}
        self.login_attempts: dict[str, list[float]] = {}
        self.access_log: list[str] = []
        self.clock: Callable[[], float] = time.monotonic
        self._seed()
        self.routes: list[tuple[str, str, Callable[..., Response]]] = [
            ("POST", "/api/login", self.login),
            ("GET", "/api/me", self.me),
            ("PATCH", "/api/profile", self.update_profile),
            ("GET", "/api/payments", self.list_payments),
            ("GET", "/api/payments/", self.get_payment),  # prefix
            ("GET", "/api/merchants/", self.get_merchant),  # prefix
            ("POST", "/api/notes", self.add_note),
            ("GET", "/notes", self.notes_page),
            ("GET", "/search", self.search_page),
            ("GET", "/files", self.get_file),
            ("GET", "/login", self.login_page),
            ("POST", "/api/webhooks/test", self.webhook_test),
            ("GET", "/settings", self.settings_page),
            ("POST", "/settings/email", self.change_email),
            ("GET", "/internal/admin", self.internal_admin),
            ("GET", "/health", lambda req: Response.json({"status": "ok"})),
            ("GET", "/boom", self.boom),
        ]

    def is_fixed(self, flaw: str) -> bool:
        return flaw in self.fixed

    # ---- data -------------------------------------------------------------------------------------------
    def _seed(self) -> None:
        hash_fn = _pbkdf2 if self.is_fixed("weak-hash") else _md5
        c = self.db
        c.executescript(
            """
            CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE, password_hash TEXT, merchant_id TEXT,
                                role TEXT, display_name TEXT);
            CREATE TABLE merchants (id TEXT PRIMARY KEY, name TEXT, api_secret TEXT, payout_iban TEXT);
            CREATE TABLE payments (id TEXT PRIMARY KEY, merchant_id TEXT, amount_minor INTEGER, currency TEXT,
                                   status TEXT, card_last4 TEXT);
            CREATE TABLE notes (id INTEGER PRIMARY KEY AUTOINCREMENT, merchant_id TEXT, body TEXT);
            """
        )
        users = [
            ("alice@shop-a.example", "alice-pass-1", "m_100", "merchant", "Alice"),
            ("bob@shop-b.example", "bob-pass-2", "m_200", "merchant", "Bob"),
            ("ops@sandpay.example", "ops-pass-3", None, "admin", "SandPay Ops"),
        ]
        for email, pw, mid, role, name in users:
            c.execute("INSERT INTO users (email, password_hash, merchant_id, role, display_name) VALUES (?,?,?,?,?)",
                      (email, hash_fn(pw), mid, role, name))
        c.executemany("INSERT INTO merchants VALUES (?,?,?,?)", [
            ("m_100", "Shop A", "sk_test_shop_a_practice", "XX00 SAND 0000 0001"),
            ("m_200", "Shop B", "sk_test_shop_b_practice", "XX00 SAND 0000 0002"),
        ])
        c.executemany("INSERT INTO payments VALUES (?,?,?,?,?,?)", [
            ("pay_1001", "m_100", 2500, "EUR", "captured", "4242"),
            ("pay_1002", "m_100", 990, "EUR", "refunded", "0005"),
            ("pay_1003", "m_100", 12000, "GBP", "authorized", "4444"),
            ("pay_2001", "m_200", 4999, "EUR", "captured", "1881"),
            ("pay_2002", "m_200", 150, "USD", "failed", "0002"),
        ])
        c.commit()

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            self.db.row_factory = sqlite3.Row
            return self.db.execute(sql, params).fetchall()

    def execute(self, sql: str, params: tuple = ()) -> None:
        with self.lock:
            self.db.execute(sql, params)
            self.db.commit()

    # ---- auth -------------------------------------------------------------------------------------------
    def current_user(self, req: Request) -> dict:
        auth = req.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            return self._user_from_jwt(auth[7:])
        sid = req.cookies.get("sid")
        if sid and sid in self.sessions:
            return self.sessions[sid]
        raise HttpError(401, "authentication required")

    def _user_from_jwt(self, token: str) -> dict:
        try:
            header_b64, payload_b64, sig_b64 = token.split(".")
            header = json.loads(_b64url_decode(header_b64))
            claims = json.loads(_b64url_decode(payload_b64))
        except (ValueError, json.JSONDecodeError) as exc:
            raise HttpError(401, "malformed token") from exc
        alg = header.get("alg")
        if alg == "none" and not self.is_fixed("jwt-none"):
            pass  # FLAW jwt-none: an unsigned token is accepted
        elif alg == "HS256":
            expected = _b64url(hmac.new(JWT_SECRET, f"{header_b64}.{payload_b64}".encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(expected, sig_b64):
                raise HttpError(401, "bad signature")
        else:
            raise HttpError(401, "unsupported alg")
        if claims.get("exp") is not None and claims["exp"] < time.time():
            raise HttpError(401, "token expired")
        rows = self.query("SELECT * FROM users WHERE email = ?", (claims.get("sub"),))
        if not rows:
            raise HttpError(401, "unknown subject")
        return dict(rows[0])

    def login(self, req: Request) -> Response:
        data = req.json()
        email, password = str(data.get("email", "")), str(data.get("password", ""))
        if self.is_fixed("secret-logging"):
            self.access_log.append(f"login attempt email={email}")
        else:
            self.access_log.append(f"login attempt email={email} password={password}")  # FLAW secret-logging
        if self.is_fixed("no-rate-limit"):
            now = self.clock()
            recent = [t for t in self.login_attempts.get(email, []) if now - t < LOGIN_WINDOW_S]
            if len(recent) >= LOGIN_LIMIT:
                resp = Response.json({"error": "too many attempts"}, 429)
                resp.headers.append(("Retry-After", str(int(LOGIN_WINDOW_S))))
                return resp
            recent.append(now)
            self.login_attempts[email] = recent
        rows = self.query("SELECT * FROM users WHERE email = ?", (email,))
        ok = False
        if rows:
            stored = rows[0]["password_hash"]
            ok = _pbkdf2_check(password, stored) if stored.startswith("pbkdf2_") else _md5(password) == stored
        if not ok:
            return Response.json({"error": "invalid email or password"}, 401)
        user = dict(rows[0])
        sid = secrets.token_urlsafe(24)
        csrf = secrets.token_urlsafe(16)
        self.sessions[sid] = {**user, "csrf": csrf}
        token = make_jwt({"sub": email, "exp": int(time.time()) + 3600})
        resp = Response.json({"token": token, "merchant_id": user["merchant_id"], "role": user["role"]})
        if self.is_fixed("weak-session"):
            resp.headers.append(("Set-Cookie", f"sid={sid}; Path=/; HttpOnly; Secure; SameSite=Lax"))
        else:
            resp.headers.append(("Set-Cookie", f"sid={sid}; Path=/"))  # FLAW weak-session
        return resp

    def me(self, req: Request) -> Response:
        u = self.current_user(req)
        return Response.json({k: u[k] for k in ("email", "merchant_id", "role", "display_name")})

    def update_profile(self, req: Request) -> Response:
        u = self.current_user(req)
        data = req.json()
        allowed = {"display_name"} if self.is_fixed("mass-assignment") else {"display_name", "role", "merchant_id"}
        rejected = sorted(set(data) - allowed)
        if rejected and self.is_fixed("mass-assignment"):
            raise HttpError(400, f"fields not allowed: {rejected}")
        for key in sorted(set(data) & allowed):
            self.execute(f"UPDATE users SET {key} = ? WHERE id = ?", (str(data[key]), u["id"]))
        row = self.query("SELECT email, merchant_id, role, display_name FROM users WHERE id = ?", (u["id"],))[0]
        for s in self.sessions.values():
            if s["id"] == u["id"]:
                s.update(dict(row))
        return Response.json(dict(row))

    # ---- payments -----------------------------------------------------------------------------------------
    def list_payments(self, req: Request) -> Response:
        u = self.current_user(req)
        status = req.query.get("status")
        if status is None:
            rows = self.query("SELECT * FROM payments WHERE merchant_id = ? ORDER BY id", (u["merchant_id"],))
        elif self.is_fixed("sqli"):
            rows = self.query("SELECT * FROM payments WHERE merchant_id = ? AND status = ? ORDER BY id",
                              (u["merchant_id"], status))
        else:
            # FLAW sqli: user input concatenated into SQL
            rows = self.query(
                f"SELECT * FROM payments WHERE merchant_id = '{u['merchant_id']}' AND status = '{status}' ORDER BY id")
        return Response.json({"data": [dict(r) for r in rows]})

    def get_payment(self, req: Request) -> Response:
        u = self.current_user(req)
        pid = req.path.rsplit("/", 1)[-1]
        rows = self.query("SELECT * FROM payments WHERE id = ?", (pid,))
        if not rows:
            raise HttpError(404, "payment not found")
        row = dict(rows[0])
        if self.is_fixed("idor") and row["merchant_id"] != u["merchant_id"] and u["role"] != "admin":
            raise HttpError(404, "payment not found")  # same answer as "missing": no existence oracle
        return Response.json(row)

    def get_merchant(self, req: Request) -> Response:
        u = self.current_user(req)
        mid = req.path.rsplit("/", 1)[-1]
        if mid != u["merchant_id"] and u["role"] != "admin":
            raise HttpError(404, "merchant not found")
        rows = self.query("SELECT * FROM merchants WHERE id = ?", (mid,))
        if not rows:
            raise HttpError(404, "merchant not found")
        row = dict(rows[0])
        if self.is_fixed("data-exposure"):
            row = {"id": row["id"], "name": row["name"], "payout_iban_last4": row["payout_iban"][-4:]}
        return Response.json(row)  # FLAW data-exposure when not fixed: api_secret and full IBAN

    # ---- pages and XSS ----------------------------------------------------------------------------------------
    def search_page(self, req: Request) -> Response:
        q = req.query.get("q", "")
        shown = html.escape(q) if self.is_fixed("xss-reflected") else q  # FLAW xss-reflected
        return Response.html(f"<!doctype html><title>Search</title><h1>Results for {shown}</h1><p>No payments.</p>")

    def add_note(self, req: Request) -> Response:
        u = self.current_user(req)
        body = str(req.json().get("body", ""))[:2000]
        self.execute("INSERT INTO notes (merchant_id, body) VALUES (?, ?)", (u["merchant_id"], body))
        return Response.json({"status": "saved"}, 201)

    def notes_page(self, req: Request) -> Response:
        u = self.current_user(req)
        rows = self.query("SELECT body FROM notes WHERE merchant_id = ? ORDER BY id", (u["merchant_id"],))
        esc = html.escape if self.is_fixed("xss-stored") else (lambda s: s)  # FLAW xss-stored
        items = "".join(f"<li>{esc(r['body'])}</li>" for r in rows)
        return Response.html(f"<!doctype html><title>Notes</title><ul>{items}</ul>")

    # ---- files, redirects, SSRF ------------------------------------------------------------------------------
    def get_file(self, req: Request) -> Response:
        name = req.query.get("name", "")
        if self.is_fixed("path-traversal"):
            if name not in FILES:
                raise HttpError(404, "file not found")
            return Response(200, FILES[name].encode(), [("Content-Type", "text/plain")])
        # FLAW path-traversal: a naive "join" over a virtual tree that resolves ../
        virtual = {**{f"public/{k}": v for k, v in FILES.items()}, SECRET_FILE: SECRET_FILE_BODY}
        parts: list[str] = ["public"]
        for part in urllib.parse.unquote(name).replace("\\", "/").split("/"):
            if part == "..":
                if parts:
                    parts.pop()
            elif part not in ("", "."):
                parts.append(part)
        resolved = "/".join(parts)
        if resolved not in virtual:
            raise HttpError(404, f"file not found: {resolved}")
        return Response(200, virtual[resolved].encode(), [("Content-Type", "text/plain")])

    def login_page(self, req: Request) -> Response:
        nxt = req.query.get("next")
        if nxt is not None:
            if self.is_fixed("open-redirect"):
                parsed = urllib.parse.urlsplit(nxt)
                if parsed.scheme or parsed.netloc or not nxt.startswith("/") or nxt.startswith("//"):
                    nxt = "/settings"
            return Response(302, b"", [("Location", nxt)])  # FLAW open-redirect when not fixed
        return Response.html("<!doctype html><title>Login</title><form method=post action=/api/login></form>")

    def webhook_test(self, req: Request) -> Response:
        self.current_user(req)
        url = str(req.json().get("url", ""))
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise HttpError(400, "url must be http(s) with a host")
        if self.is_fixed("ssrf"):
            try:
                ip = ipaddress.ip_address(parsed.hostname)
            except ValueError:
                ip = None
            if parsed.hostname in LOOPBACK or (ip is not None and (ip.is_private or ip.is_loopback or ip.is_link_local)):
                raise HttpError(400, "webhook url must be a public address")
            # Practice app: never leaves the machine, even for "public" addresses.
            return Response.json({"delivered": False, "reason": "outbound calls disabled in practice"})
        # FLAW ssrf: the server fetches whatever URL it is given. Practice safety: only loopback is fetched.
        if parsed.hostname not in LOOPBACK:
            return Response.json({"delivered": False, "reason": "outbound calls disabled in practice"})
        with urllib.request.urlopen(url, timeout=2) as r:  # noqa: S310 - loopback only, see above
            body = r.read(4096).decode(errors="replace")
        return Response.json({"delivered": True, "status": r.status, "response_preview": body[:500]})

    def internal_admin(self, req: Request) -> Response:
        # Meant for the internal network only - "protected" by trusting loopback callers (the SSRF target).
        if req.headers.get("x-forwarded-for") is None and self._peer_is_loopback:
            return Response.json({"admin": True, "settlement_key": "sk_practice_do_not_use"})
        raise HttpError(403, "internal only")

    _peer_is_loopback = True  # every caller is loopback in practice; the SSRF lesson explains the real case

    # ---- CSRF ----------------------------------------------------------------------------------------------
    def settings_page(self, req: Request) -> Response:
        # A browser page: it needs the cookie session (bearer-token API clients have no CSRF token or form).
        sid = req.cookies.get("sid")
        if not sid or sid not in self.sessions:
            raise HttpError(401, "sign in with a browser session (cookie sid)")
        u = self.sessions[sid]
        token_field = f'<input type="hidden" name="csrf" value="{u["csrf"]}">' if self.is_fixed("csrf") else ""
        return Response.html(
            "<!doctype html><title>Settings</title>"
            f'<form method="post" action="/settings/email">{token_field}'
            '<input name="email"><button>Save</button></form>')

    def change_email(self, req: Request) -> Response:
        sid = req.cookies.get("sid")
        if not sid or sid not in self.sessions:
            raise HttpError(401, "authentication required")
        u = self.sessions[sid]
        form = req.form()
        if self.is_fixed("csrf") and not hmac.compare_digest(form.get("csrf", ""), u["csrf"]):
            raise HttpError(403, "missing or wrong CSRF token")
        new_email = form.get("email", "")
        if "@" not in new_email:
            raise HttpError(400, "invalid email")
        self.execute("UPDATE users SET email = ? WHERE id = ?", (new_email, u["id"]))
        u["email"] = new_email
        return Response.json({"email": new_email})

    def boom(self, req: Request) -> Response:
        raise RuntimeError(f"settlement batch failed; db=sqlite:///var/sandpay/portal.db key={JWT_SECRET.decode()}")

    # ---- dispatch ------------------------------------------------------------------------------------------
    def handle(self, req: Request) -> Response:
        try:
            resp = self._route(req)
        except HttpError as e:
            resp = Response.json({"error": e.message}, e.status)
        except Exception:  # noqa: BLE001
            if self.is_fixed("verbose-errors"):
                ref = secrets.token_hex(4)
                resp = Response.json({"error": "internal error", "reference": ref}, 500)
            else:
                resp = Response(500, traceback.format_exc().encode(), [("Content-Type", "text/plain")])
        if self.is_fixed("missing-headers"):
            resp.headers += [
                ("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'"),
                ("X-Content-Type-Options", "nosniff"),
                ("Referrer-Policy", "no-referrer"),
                ("Strict-Transport-Security", "max-age=31536000"),
            ]
        self.access_log.append(f"{req.method} {req.path} {resp.status}")
        return resp

    def _route(self, req: Request) -> Response:
        for method, path, fn in self.routes:
            exact = req.path == path
            prefix = path.endswith("/") and req.path.startswith(path) and len(req.path) > len(path)
            if (exact or prefix) and req.method == method:
                return fn(req)
        if any(req.path == p or (p.endswith("/") and req.path.startswith(p)) for _, p, _ in self.routes):
            raise HttpError(405, "method not allowed")
        raise HttpError(404, "not found")


def make_app(fixed: set[str] | frozenset[str] | tuple[str, ...] = ()) -> App:
    """The vulnerable app; ``fixed`` names the flaws to fix (see ``FLAWS``). ``make_app(FLAWS)`` fixes all."""
    return App(frozenset(fixed))


def _handler_for(app: App) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        # Headers and body go out as separate writes; without this, Nagle + delayed ACK add ~40 ms per keep-alive request.
        disable_nagle_algorithm = True

        def _serve(self) -> None:
            split = urllib.parse.urlsplit(self.path)
            length = int(self.headers.get("Content-Length") or 0)
            cookies = {k: m.value for k, m in SimpleCookie(self.headers.get("Cookie", "")).items()}
            req = Request(self.command, split.path, {k: v[0] for k, v in urllib.parse.parse_qs(split.query).items()},
                          {k.lower(): v for k, v in self.headers.items()}, self.rfile.read(length), cookies)
            resp = app.handle(req)
            self.send_response(resp.status)
            for name, value in resp.headers:
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(resp.body)))
            self.end_headers()
            self.wfile.write(resp.body)

        def version_string(self) -> str:
            # FLAW missing-headers also covers version disclosure: the default reveals the stack and versions.
            return "SandPay" if app.is_fixed("missing-headers") else "SandPayPortal/0.9 Python/3.12"

        do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = _serve

        def log_message(self, format: str, *args: Any) -> None:  # keep test output quiet
            pass

    return Handler


@contextlib.contextmanager
def serve(app: App, host: str = "127.0.0.1", port: int = 0) -> Iterator[str]:
    """Serves ``app`` on the loopback interface in a background thread; yields the base URL."""
    if host not in LOOPBACK:
        raise ValueError("the vulnerable practice app only binds to the loopback interface")
    server = ThreadingHTTPServer((host, port), _handler_for(app))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="SandPay deliberately vulnerable practice portal (loopback only)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--fix", action="append", default=[], choices=FLAWS, help="fix a flaw (repeatable)")
    parser.add_argument("--fix-all", action="store_true")
    args = parser.parse_args()
    app = make_app(FLAWS if args.fix_all else args.fix)
    with serve(app, port=args.port) as url:
        print(f"SandPay practice portal on {url} (fixed: {sorted(app.fixed) or 'none'}) - Ctrl+C to stop", flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
