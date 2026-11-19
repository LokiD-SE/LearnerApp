"""Checks exercises/foundations/recon_crawler.py: a read-only crawler that stays in scope (WSTG-INFO-07)."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests
from foundations.recon_crawler import crawl, in_scope, path_of
from sandpay_vuln import FLAWS, make_app, serve

pytestmark = pytest.mark.exercise

SEEDS = ["/login", "/login?next=https://evil.example/", "/search?q=test", "/files?name=terms.txt", "/health"]

# A tiny static site for link-following, hidden fields and max_pages (the portal itself has few links).
STATIC = {
    "/": '<a href="/a">A</a> <a href="/b?x=1">B</a> <a href="https://cdn.example/lib.js">CDN</a> <a href="/a">A again</a>',
    "/a": '<form action="/pay" method="post"><input type="hidden" name="nonce" value="n-1">'
          '<input name="amount"></form><a href="/c">C</a>',
    "/b": '<form action="https://partner.example/collect"><input name="ref" value="r"></form>',
    "/c": "<p>end</p>",
}


@pytest.fixture
def static_site():
    requests_seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            requests_seen.append(("GET", self.path))
            body = STATIC.get(self.path.split("?")[0])
            self.send_response(200 if body else 404)
            self.send_header("Content-Type", "text/html")
            data = (body or "missing").encode()
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):  # noqa: N802
            requests_seen.append(("POST", self.path))
            self.send_response(500)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", requests_seen
    server.shutdown()
    server.server_close()


def test_path_of_keeps_path_and_query():
    assert path_of("http://127.0.0.1:8765/files?name=a") == "/files?name=a"
    assert path_of("http://127.0.0.1:8765") == "/"


@pytest.mark.parametrize("url,expected", [
    ("http://127.0.0.1:8765/x", True),
    ("http://127.0.0.1:8766/x", False),  # another port is another service
    ("https://127.0.0.1:8765/x", False),  # another scheme
    ("http://localhost:8765/x", False),  # same machine, but not the origin in scope
    ("https://evil.example/", False),
])
def test_in_scope_is_the_exact_origin(url, expected):
    assert in_scope(url, "http://127.0.0.1:8765") is expected


def test_maps_the_portal_pages():
    with serve(make_app()) as base:
        site = crawl(base, SEEDS)
    assert site.pages == {"/login": 200, "/login?next=https://evil.example/": 302, "/search?q=test": 200,
                          "/files?name=terms.txt": 200, "/health": 200}
    assert site.content_types["/health"] == "application/json"
    assert [(f.page, f.method, f.action) for f in site.forms] == [("/login", "POST", "/api/login")]


def test_an_open_redirect_is_recorded_but_never_followed_out_of_scope():
    with serve(make_app()) as base:
        site = crawl(base, SEEDS)
    assert site.redirects == {"/login?next=https://evil.example/": "https://evil.example/"}
    assert site.out_of_scope == {"https://evil.example/"}


def test_an_in_scope_redirect_is_followed():
    with serve(make_app(FLAWS)) as base:  # fixed: next= is rewritten to a local path
        site = crawl(base, SEEDS)
    assert site.redirects == {"/login?next=https://evil.example/": "/settings"}
    assert site.pages["/settings"] == 401
    assert site.out_of_scope == set()


def test_records_forms_without_submitting_them():
    app = make_app()
    with serve(app) as base:
        s = requests.Session()
        s.post(f"{base}/api/login", json={"email": "alice@shop-a.example", "password": "alice-pass-1"})
        before = len(app.access_log)
        site = crawl(base, ["/settings", "/notes"], session=s)
        during = app.access_log[before:]
    assert [(f.page, f.method, f.action, f.fields) for f in site.forms] == [
        ("/settings", "POST", "/settings/email", [("email", "text", "")])]
    assert during and all(line.startswith("GET ") for line in during), during


def test_follows_links_once_records_hidden_fields_and_external_targets(static_site):
    base, seen = static_site
    site = crawl(base, ["/"])
    assert set(site.pages) == {"/", "/a", "/b?x=1", "/c"}
    assert all(method == "GET" for method, _ in seen)
    assert len(seen) == 4  # /a is linked twice but fetched once
    forms = {f.page: f for f in site.forms}
    assert forms["/a"].action == "/pay" and forms["/a"].method == "POST"
    assert ("nonce", "hidden", "n-1") in forms["/a"].fields
    assert forms["/b?x=1"].action == "https://partner.example/collect" and forms["/b?x=1"].method == "GET"
    assert site.out_of_scope == {"https://cdn.example/lib.js", "https://partner.example/collect"}


def test_stops_at_max_pages(static_site):
    base, seen = static_site
    site = crawl(base, ["/"], max_pages=2)
    assert len(site.pages) == 2 and len(seen) == 2
