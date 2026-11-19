"""Checks exercises/foundations/recon_entry_points.py: an entry-point inventory that changes nothing
(WSTG-INFO-06)."""

import pytest
from foundations.recon_entry_points import Candidate, classify, inventory, login_token
from sandpay_vuln import make_app, serve

pytestmark = pytest.mark.exercise

CANDIDATES = [
    Candidate("GET", "/health"),
    Candidate("GET", "/search?q=test", ("q",)),
    Candidate("GET", "/files?name=terms.txt", ("name",)),
    Candidate("GET", "/api/me"),
    Candidate("GET", "/api/payments", ("status",)),
    Candidate("GET", "/api/payments/pay_1001"),
    Candidate("POST", "/api/notes", ("body",)),
    Candidate("PATCH", "/api/profile", ("display_name",)),
    Candidate("POST", "/api/webhooks/test", ("url",)),
    Candidate("POST", "/settings/email", ("email",)),
    Candidate("GET", "/api/login"),
    Candidate("GET", "/admin"),
]

EXPECTED = [
    ("GET", "/admin", 404, 404, "missing"),
    ("GET", "/api/login", 405, 405, "method-not-allowed"),
    ("GET", "/api/me", 401, 200, "authenticated"),
    ("POST", "/api/notes", 401, None, "authenticated"),
    ("GET", "/api/payments", 401, 200, "authenticated"),
    ("GET", "/api/payments/pay_1001", 401, 200, "authenticated"),
    ("PATCH", "/api/profile", 401, None, "authenticated"),
    ("POST", "/api/webhooks/test", 401, None, "authenticated"),
    ("GET", "/files?name=terms.txt", 200, 200, "public"),
    ("GET", "/health", 200, 200, "public"),
    ("GET", "/search?q=test", 200, 200, "public"),
    ("POST", "/settings/email", 401, None, "authenticated"),
]


@pytest.mark.parametrize("anonymous,authenticated,expected", [
    (200, 200, "public"),
    (401, 200, "authenticated"),
    (403, 200, "authenticated"),
    (401, None, "authenticated"),
    (404, 404, "missing"),
    (404, None, "missing"),
    (404, 200, "public"),  # hidden from anonymous callers with a 404, but there: not "missing"
    (405, 405, "method-not-allowed"),
    (500, 500, "error"),
    (302, 302, "public"),
])
def test_classify(anonymous, authenticated, expected):
    assert classify(anonymous, authenticated) == expected


def test_inventory_of_the_portal():
    with serve(make_app()) as base:
        token = login_token(base, "alice@shop-a.example", "alice-pass-1")
        rows = inventory(base, CANDIDATES, token)
    assert [(e.method, e.path, e.anonymous, e.authenticated, e.access) for e in rows] == EXPECTED
    assert next(e for e in rows if e.path == "/api/notes").params == ("body",)


def test_recon_changes_nothing():
    app = make_app()
    with serve(app) as base:
        token = login_token(base, "alice@shop-a.example", "alice-pass-1")
        inventory(base, CANDIDATES, token)
    assert app.query("SELECT COUNT(*) FROM notes")[0][0] == 0
    alice = app.query("SELECT email, role, display_name FROM users WHERE id = 1")[0]
    assert tuple(alice) == ("alice@shop-a.example", "merchant", "Alice")


def test_unsafe_methods_are_never_sent_with_credentials():
    sent = []
    app = make_app()
    original = app.handle

    def spy(req):
        sent.append((req.method, "authorization" in req.headers))
        return original(req)

    app.handle = spy
    with serve(app) as base:
        token = login_token(base, "alice@shop-a.example", "alice-pass-1")
        sent.clear()
        inventory(base, CANDIDATES, token)
    assert sent, "no requests were sent"
    assert not [m for m, auth in sent if auth and m not in ("GET", "HEAD")]
