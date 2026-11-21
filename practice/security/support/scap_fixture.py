"""Shared pieces of the capstone (lesson security-testing-capstone): types, scope rule, probes and the catalogue.

Everything here runs against the practice portal (``support/sandpay_vuln.py``) on loopback. The exercises in
``exercises/specialised/scap_*.py`` build the assessment around this module:

- ``scap_scope.GuardedHttp``   the HTTP wrapper that enforces the rules of engagement (you write it);
- ``scap_assess``              runs the probes through the wrapper and turns results into scored findings (you write it);
- ``scap_retest``              compares two assessments after the fixes (you write it).

What is NOT an exercise lives here, so the capstone does not depend on any other exercise being solved:

- ``check_scope``  the scope rule from the foundations lesson, as one function (the full version with its tests is
  ``foundations/fund_scope.py``);
- ``PROBES``       one probe per flaw that can be seen from outside, in the style of the earlier lessons: a
  POSITIVE CONTROL first (``ControlFailed`` when it fails), harmless values only, evidence that never contains a
  secret;
- ``whitebox_results``  the two flaws a black-box test cannot see (``weak-hash``, ``secret-logging``), checked from
  evidence the owner supplies;
- ``CATALOGUE``    title, CWE and CVSS v4.0 vector per flaw, and ``SCORES`` the pinned base score of each vector
  (computed with ``solutions/specialised/cvss_v4.py``; ``scap_demo.py`` re-checks them).
"""

from __future__ import annotations

import base64
import json
import posixpath
import urllib.parse
from dataclasses import dataclass, field
from typing import Callable

import requests

ALICE = ("alice@shop-a.example", "alice-pass-1")  # merchant m_100
BOB = ("bob@shop-b.example", "bob-pass-2")  # merchant m_200
USERS = {"alice": ALICE, "bob": BOB}
LOOPBACK = ("127.0.0.1", "localhost", "::1")
CANARY = "<i>scap-canary</i>"  # harmless markup used to see whether output is encoded
NO_BODY_SECRETS = "values are never recorded"

STATUSES = ("found", "not-found", "inconclusive", "blocked", "not-run")


class OutOfScope(Exception):
    """A request the rules of engagement do not allow."""


class BudgetExhausted(OutOfScope):
    """The request budget of the engagement is used up."""


class ControlFailed(Exception):
    """A probe's positive control failed: the probe proved nothing about the flaw."""


@dataclass(frozen=True)
class Scope:
    """The technical part of the rules of engagement for the capstone."""

    base_url: str
    methods: frozenset[str] = frozenset({"GET", "POST", "PATCH"})
    excluded_paths: tuple[str, ...] = ("/internal/",)
    max_requests: int = 150


def make_scope(base_url: str, **changes) -> Scope:
    return Scope(base_url=base_url, **changes)


def check_scope(scope: Scope, method: str, url: str) -> str | None:
    """None when ``method url`` is allowed, otherwise the reason it is refused.

    The foundations lesson builds this rule and its tests (``fund_scope.check``); this is the same rule in one
    function: http only, no user info, the exact host and port of ``scope.base_url``, a loopback host, an allowed
    method, and no excluded path prefix after percent-decoding and ``..`` folding.
    """
    base = urllib.parse.urlsplit(scope.base_url)
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "http":
        return f"scheme {parts.scheme or '(none)'!r} is not http"
    if parts.username is not None or "@" in parts.netloc:
        return "user info in the URL hides the real host"
    if (parts.hostname or "").lower() not in LOOPBACK:
        return f"host {parts.hostname!r} is not a loopback address (practice rule)"
    if parts.hostname != base.hostname or parts.port != base.port:
        return f"{parts.hostname}:{parts.port} is not the engagement target {base.hostname}:{base.port}"
    if method.upper() not in scope.methods:
        return f"method {method.upper()} is not allowed"
    path = posixpath.normpath("/" + urllib.parse.unquote(parts.path).lstrip("/"))
    for prefix in scope.excluded_paths:
        if (path + "/").startswith(prefix):
            return f"path {path} is excluded from the scope"
    return None


@dataclass(frozen=True)
class Result:
    flaw: str
    status: str  # one of STATUSES
    evidence: str
    requests: int = 0


@dataclass(frozen=True)
class Assessment:
    results: tuple[Result, ...]

    def get(self, flaw: str) -> Result | None:
        return next((r for r in self.results if r.flaw == flaw), None)

    def found(self) -> list[str]:
        return [r.flaw for r in self.results if r.status == "found"]


@dataclass(frozen=True)
class Retest:
    flaw: str
    outcome: str  # fixed, still-open, new, unverified, unchanged, newly-tested
    note: str


def rating(score: float) -> str:
    """The CVSS qualitative scale (None 0.0, Low 0.1-3.9, Medium 4.0-6.9, High 7.0-8.9, Critical 9.0-10.0)."""
    if score == 0.0:
        return "None"
    if score < 4.0:
        return "Low"
    if score < 7.0:
        return "Medium"
    if score < 9.0:
        return "High"
    return "Critical"


# ---- the context probes share ---------------------------------------------------------------------------------


class Context:
    """What a probe is given: guarded requests, and a login that happens once per user.

    Logging in again for every probe would burn the portal's login limit (5 attempts per account per minute once
    ``no-rate-limit`` is fixed) and make a control fail for a reason that has nothing to do with the flaw.
    """

    def __init__(self, http):
        self.http = http
        self._sessions: dict[str, dict] = {}

    def login(self, user: str) -> dict:
        if user not in self._sessions:
            email, password = USERS[user]
            resp = self.http.request("POST", "/api/login", json={"email": email, "password": password})
            if resp.status_code != 200:
                raise ControlFailed(f"control failed: login as {user} answered {resp.status_code}")
            set_cookie = resp.headers.get("Set-Cookie", "")
            sid = set_cookie.split(";", 1)[0].removeprefix("sid=")
            self._sessions[user] = {"token": resp.json()["token"], "set_cookie": set_cookie, "sid": sid}
        return self._sessions[user]

    def call(self, method: str, path: str, as_: str | None = None, **kw):
        if as_ is not None:
            kw["headers"] = {**kw.get("headers", {}), "Authorization": f"Bearer {self.login(as_)['token']}"}
        return self.http.request(method, path, **kw)

    def get(self, path: str, as_: str | None = None, **kw):
        return self.call("GET", path, as_, **kw)


Probe = Callable[[Context], "str | None"]


def _b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


# ---- probes: one per flaw that can be seen from outside ---------------------------------------------------


def probe_idor(ctx: Context) -> str | None:
    own = ctx.get("/api/payments/pay_1001", as_="alice")
    if own.status_code != 200 or own.json().get("merchant_id") != "m_100":
        raise ControlFailed("control failed: alice cannot read her own payment")
    other = ctx.get("/api/payments/pay_2001", as_="alice")
    if other.status_code == 200 and other.json().get("merchant_id") == "m_200":
        return "alice (merchant m_100) read pay_2001 of merchant m_200: GET /api/payments/pay_2001 -> 200"
    return None


def probe_mass_assignment(ctx: Context) -> str | None:
    me = ctx.get("/api/me", as_="bob")
    if me.status_code != 200 or me.json().get("role") != "merchant":
        raise ControlFailed("control failed: /api/me did not show bob as a merchant")
    # Same-value probe: the protected field is sent with the value it already has, so nothing changes.
    resp = ctx.call("PATCH", "/api/profile", as_="bob", json={"role": "merchant"})
    if resp.status_code == 200 and resp.json().get("role") == "merchant":
        return "PATCH /api/profile accepted the protected field role (the current value was sent, nothing changed)"
    return None


def probe_sqli(ctx: Context) -> str | None:
    base = ctx.get("/api/payments", as_="alice", params={"status": "captured"})
    rows = base.json().get("data", []) if base.status_code == 200 else None
    if not rows or any(r["merchant_id"] != "m_100" for r in rows):
        raise ControlFailed("control failed: a plain status filter did not return only alice's rows")
    tautology = ctx.get("/api/payments", as_="alice", params={"status": "captured' OR '1'='1"})
    if tautology.status_code == 200:
        merchants = {r["merchant_id"] for r in tautology.json().get("data", [])}
        if merchants - {"m_100"}:
            return f"a tautology in ?status= returned rows of merchants {sorted(merchants)}; alice owns m_100"
    return None


def probe_xss_reflected(ctx: Context) -> str | None:
    plain = ctx.get("/search", params={"q": "scap-plain"})
    if plain.status_code != 200 or "scap-plain" not in plain.text:
        raise ControlFailed("control failed: /search did not echo a plain word")
    resp = ctx.get("/search", params={"q": CANARY})
    if CANARY in resp.text:
        return "GET /search?q= returned the canary markup unencoded"
    return None


def probe_xss_stored(ctx: Context) -> str | None:
    saved = ctx.call("POST", "/api/notes", as_="alice", json={"body": CANARY})
    if saved.status_code != 201:
        raise ControlFailed(f"control failed: saving a note answered {saved.status_code}")
    page = ctx.get("/notes", as_="alice")
    if CANARY in page.text:
        return "GET /notes returned a stored canary note unencoded"
    return None


def probe_path_traversal(ctx: Context) -> str | None:
    ok = ctx.get("/files", params={"name": "terms.txt"})
    if ok.status_code != 200 or "merchant terms" not in ok.text:
        raise ControlFailed("control failed: a public file was not served as expected")
    bad = ctx.get("/files", params={"name": "../internal/settlement-keys.txt"})
    if bad.status_code == 200 and "SETTLEMENT_SIGNING_KEY=" in bad.text:
        return "GET /files?name=../internal/... served the internal settlement-keys file (contents not recorded)"
    return None


def probe_open_redirect(ctx: Context) -> str | None:
    ok = ctx.get("/login", params={"next": "/settings"})
    if ok.status_code != 302 or ok.headers.get("Location") != "/settings":
        raise ControlFailed("control failed: a local next= was not redirected as expected")
    bad = ctx.get("/login", params={"next": "https://evil.example/"})
    if bad.status_code == 302 and urllib.parse.urlsplit(bad.headers.get("Location", "")).netloc == "evil.example":
        return "GET /login?next= redirects to another site (the redirect was not followed)"
    return None


def probe_ssrf(ctx: Context) -> str | None:
    outside = ctx.call("POST", "/api/webhooks/test", as_="alice", json={"url": "https://api.sandpay.example/hook"})
    if outside.status_code != 200 or outside.json().get("delivered") is not False:
        raise ControlFailed("control failed: the webhook test did not answer for a public URL")
    target = ctx.http.scope.base_url + "/health"  # the target's own health page: in scope, harmless
    resp = ctx.call("POST", "/api/webhooks/test", as_="alice", json={"url": target})
    if resp.status_code == 200 and resp.json().get("delivered") is True and "ok" in resp.json().get("response_preview", ""):
        return "POST /api/webhooks/test fetched an internal URL for us and returned its body (the target's /health)"
    return None


def probe_csrf(ctx: Context) -> str | None:
    sid = ctx.login("alice")["sid"]
    cookie = {"Cookie": f"sid={sid}"}  # sent by hand: the fixed portal's cookie is Secure, requests would drop it on http
    page = ctx.get("/settings", headers=cookie)
    if page.status_code != 200:
        raise ControlFailed(f"control failed: /settings answered {page.status_code} with the session cookie")
    # Same-value probe: the account's current email is sent back, so nothing changes.
    resp = ctx.call("POST", "/settings/email", headers=cookie, data={"email": ALICE[0]})
    if resp.status_code == 200:
        return "POST /settings/email without a CSRF token was accepted (the current email was sent, nothing changed)"
    return None


def probe_weak_session(ctx: Context) -> str | None:
    set_cookie = ctx.login("alice")["set_cookie"]
    if not set_cookie.startswith("sid="):
        raise ControlFailed("control failed: the login did not set a sid cookie")
    flags = {part.strip().split("=")[0].lower() for part in set_cookie.split(";")[1:]}
    missing = [name for name in ("HttpOnly", "Secure", "SameSite") if name.lower() not in flags]
    if missing:
        return f"the session cookie lacks the attributes {', '.join(missing)} (the cookie value is not recorded)"
    return None


def probe_no_rate_limit(ctx: Context) -> str | None:
    statuses = []
    for _ in range(7):  # an account that does not exist: nothing real can be locked or guessed
        resp = ctx.http.request("POST", "/api/login", json={"email": "nobody@shop-a.example", "password": "scap-wrong"})
        statuses.append(resp.status_code)
    if statuses[0] != 401:
        raise ControlFailed(f"control failed: a bad login answered {statuses[0]} instead of 401")
    if 429 not in statuses:
        return "7 failed logins for one account in a row; none was answered 429"
    return None


def probe_jwt_none(ctx: Context) -> str | None:
    valid = ctx.get("/api/me", as_="alice")
    if valid.status_code != 200:
        raise ControlFailed("control failed: a signed token was not accepted")
    unsigned = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64({'sub': ALICE[0]})}."
    resp = ctx.get("/api/me", headers={"Authorization": f"Bearer {unsigned}"})
    if resp.status_code == 200 and resp.json().get("email") == ALICE[0]:
        return "GET /api/me accepted a token with alg none and no signature"
    return None


def probe_verbose_errors(ctx: Context) -> str | None:
    if ctx.get("/health").status_code != 200:
        raise ControlFailed("control failed: /health did not answer 200")
    resp = ctx.get("/boom")
    if "Traceback" in resp.text:
        secret_line = " and a line naming a key" if "key=" in resp.text else ""
        return f"GET /boom returned a stack trace{secret_line} (the text is not recorded)"
    return None


def probe_missing_headers(ctx: Context) -> str | None:
    resp = ctx.get("/health")
    if resp.status_code != 200:
        raise ControlFailed("control failed: /health did not answer 200")
    wanted = ("Content-Security-Policy", "X-Content-Type-Options", "Referrer-Policy", "Strict-Transport-Security")
    missing = [h for h in wanted if h not in resp.headers]
    if missing:
        return f"GET /health lacks the response headers {', '.join(missing)}"
    return None


def probe_data_exposure(ctx: Context) -> str | None:
    resp = ctx.get("/api/merchants/m_100", as_="alice")
    if resp.status_code != 200:
        raise ControlFailed(f"control failed: alice could not read her own merchant record ({resp.status_code})")
    exposed = [k for k in ("api_secret", "payout_iban") if k in resp.json()]
    if exposed:
        return f"GET /api/merchants/m_100 returns the fields {', '.join(exposed)} to the browser ({NO_BODY_SECRETS})"
    return None


PROBES: dict[str, Probe] = {
    "idor": probe_idor,
    "mass-assignment": probe_mass_assignment,
    "sqli": probe_sqli,
    "xss-reflected": probe_xss_reflected,
    "xss-stored": probe_xss_stored,
    "path-traversal": probe_path_traversal,
    "open-redirect": probe_open_redirect,
    "ssrf": probe_ssrf,
    "csrf": probe_csrf,
    "weak-session": probe_weak_session,
    "no-rate-limit": probe_no_rate_limit,
    "jwt-none": probe_jwt_none,
    "verbose-errors": probe_verbose_errors,
    "missing-headers": probe_missing_headers,
    "data-exposure": probe_data_exposure,
}

BLACKBOX_FLAWS = tuple(PROBES)
WHITEBOX_FLAWS = ("weak-hash", "secret-logging")


def whitebox_results(app) -> list[Result]:
    """The two flaws no request can show, checked from evidence the OWNER supplies (a database extract, a log).

    ``app`` is the practice portal object; in a real engagement the owner hands over a hash extract and a log sample
    under the rules of engagement. Nothing here prints a hash or a log line: only counts and a verdict.
    """
    hashes = [r["password_hash"] for r in app.query("SELECT password_hash FROM users")]
    md5_like = [h for h in hashes if len(h) == 32 and all(c in "0123456789abcdef" for c in h)]
    weak = Result(
        "weak-hash",
        "found" if md5_like else "not-found",
        f"{len(md5_like)} of {len(hashes)} stored password hashes are 32-hex digests with no salt or cost marker",
    )
    leaked = [line for line in app.access_log if "password=" in line]
    logging_result = Result(
        "secret-logging",
        "found" if leaked else "not-found",
        f"{len(leaked)} access-log lines contain the text 'password=' (lines not recorded)",
    )
    return [weak, logging_result]


# ---- catalogue: how each flaw is reported -----------------------------------------------------------------

CATALOGUE: dict[str, dict] = {
    "idor": {"title": "Merchants can read each other's payments", "cwe": "CWE-639",
             "vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N"},
    "mass-assignment": {"title": "A merchant can send the protected field role to the profile endpoint", "cwe": "CWE-915",
                        "vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:H/VI:H/VA:N/SC:N/SI:N/SA:N"},
    "sqli": {"title": "SQL injection in the payment status filter", "cwe": "CWE-89",
             "vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N"},
    "xss-reflected": {"title": "Reflected cross-site scripting in the search page", "cwe": "CWE-79",
                      "vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:A/VC:N/VI:N/VA:N/SC:L/SI:L/SA:N"},
    "xss-stored": {"title": "Stored cross-site scripting in merchant notes", "cwe": "CWE-79",
                   "vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:A/VC:N/VI:N/VA:N/SC:L/SI:L/SA:N"},
    "path-traversal": {"title": "Path traversal reaches the internal settlement keys file", "cwe": "CWE-22",
                       "vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N"},
    "open-redirect": {"title": "Login redirect to any site", "cwe": "CWE-601",
                      "vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:P/VC:N/VI:N/VA:N/SC:L/SI:L/SA:N"},
    "ssrf": {"title": "The webhook test fetches internal URLs for the caller", "cwe": "CWE-918",
             "vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N"},
    "csrf": {"title": "No CSRF protection on the email change", "cwe": "CWE-352",
             "vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:P/VC:N/VI:H/VA:N/SC:N/SI:N/SA:N"},
    "weak-session": {"title": "Session cookie without HttpOnly, Secure or SameSite", "cwe": "CWE-1004",
                     "vector": "CVSS:4.0/AV:N/AC:H/AT:P/PR:N/UI:P/VC:L/VI:L/VA:N/SC:N/SI:N/SA:N"},
    "no-rate-limit": {"title": "No limit on failed logins", "cwe": "CWE-307",
                      "vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:L/VI:L/VA:N/SC:N/SI:N/SA:N"},
    "jwt-none": {"title": "Unsigned tokens (alg none) are accepted", "cwe": "CWE-347",
                 "vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:N/SC:N/SI:N/SA:N"},
    "verbose-errors": {"title": "Stack traces with an application key in error responses", "cwe": "CWE-209",
                       "vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N"},
    "missing-headers": {"title": "Security response headers are missing", "cwe": "CWE-693",
                        "vector": "CVSS:4.0/AV:N/AC:H/AT:P/PR:N/UI:P/VC:N/VI:N/VA:N/SC:L/SI:N/SA:N"},
    "data-exposure": {"title": "Merchant record returns the API secret and full IBAN", "cwe": "CWE-200",
                      "vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:L/VI:N/VA:N/SC:N/SI:N/SA:N"},
    "weak-hash": {"title": "Passwords stored as unsalted MD5", "cwe": "CWE-916",
                  "vector": "CVSS:4.0/AV:N/AC:H/AT:P/PR:H/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N"},
    "secret-logging": {"title": "Passwords written to the access log", "cwe": "CWE-532",
                       "vector": "CVSS:4.0/AV:L/AC:L/AT:N/PR:H/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N"},
}

# Pinned base scores of the vectors above, from solutions/specialised/cvss_v4.py (see support/scap_demo.py).
SCORES: dict[str, float] = {
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N": 7.1,  # idor
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:H/VI:H/VA:N/SC:N/SI:N/SA:N": 8.6,  # mass-assignment
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N": 7.1,  # sqli
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:A/VC:N/VI:N/VA:N/SC:L/SI:L/SA:N": 5.1,  # xss-reflected
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:A/VC:N/VI:N/VA:N/SC:L/SI:L/SA:N": 4.8,  # xss-stored
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N": 8.7,  # path-traversal
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:P/VC:N/VI:N/VA:N/SC:L/SI:L/SA:N": 5.3,  # open-redirect
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N": 7.1,  # ssrf
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:P/VC:N/VI:H/VA:N/SC:N/SI:N/SA:N": 7.1,  # csrf
    "CVSS:4.0/AV:N/AC:H/AT:P/PR:N/UI:P/VC:L/VI:L/VA:N/SC:N/SI:N/SA:N": 2.3,  # weak-session
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:L/VI:L/VA:N/SC:N/SI:N/SA:N": 6.9,  # no-rate-limit
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:N/SC:N/SI:N/SA:N": 9.3,  # jwt-none
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N": 8.7,  # verbose-errors
    "CVSS:4.0/AV:N/AC:H/AT:P/PR:N/UI:P/VC:N/VI:N/VA:N/SC:L/SI:N/SA:N": 2.3,  # missing-headers
    "CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:L/VI:N/VA:N/SC:N/SI:N/SA:N": 5.3,  # data-exposure
    "CVSS:4.0/AV:N/AC:H/AT:P/PR:H/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N": 5.9,  # weak-hash
    "CVSS:4.0/AV:L/AC:L/AT:N/PR:H/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N": 6.7,  # secret-logging
}


def score_of(vector: str) -> float:
    """Pinned score of a catalogue vector. Raises ValueError for any other vector (this is not a scorer)."""
    try:
        return SCORES[vector]
    except KeyError as exc:
        raise ValueError(f"no pinned score for {vector!r}") from exc


@dataclass(frozen=True)
class LogEntry:
    method: str
    path: str  # path only: query strings can carry values that must not be copied into evidence
    status: int


class BareHttp:
    """An HTTP wrapper with NO rules: it only counts and sends. The tests of the assessment and retest exercises use
    it so they do not depend on your ``GuardedHttp``; the lesson uses it to show what the guard prevents.

    ``limit`` makes it raise ``BudgetExhausted`` after that many requests (a stand-in for a budget);
    ``blocked`` is a set of path prefixes it refuses with ``OutOfScope`` (a stand-in for exclusions).
    """

    def __init__(self, scope: Scope, limit: int | None = None, blocked: tuple[str, ...] = ()):
        self.scope = scope
        self.limit = limit
        self.blocked = blocked
        self.log: list[LogEntry] = []
        self._session = requests.Session()

    @property
    def used(self) -> int:
        return len(self.log)

    def request(self, method: str, target: str, **kw):
        if self.limit is not None and self.used >= self.limit:
            raise BudgetExhausted("request budget exhausted")
        if any(target.startswith(p) for p in self.blocked):
            raise OutOfScope(f"{target} is excluded")
        url = self.scope.base_url + target if target.startswith("/") else target
        kw.pop("allow_redirects", None)
        resp = self._session.request(method.upper(), url, allow_redirects=False, timeout=5, **kw)
        self.log.append(LogEntry(method.upper(), urllib.parse.urlsplit(url).path, resp.status_code))
        return resp
