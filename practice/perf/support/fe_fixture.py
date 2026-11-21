"""A small local SandPay checkout page in two versions, for the frontend performance lesson (loopback only).

``serve()`` starts one server with two copies of the same page:

* ``/slow/``  - what many pages look like: a render-blocking stylesheet and a synchronous script in the head, the
  hero image added later by JavaScript (so the browser discovers it late) without width and height, and a late
  widget that blocks the main thread for 200 ms in one go, and a click handler that blocks it for 120 ms.
* ``/fixed/`` - the same page with the usual fixes: critical CSS inline, scripts deferred (the start-up work in 30 ms chunks), the hero image in the
  HTML with its size and a high fetch priority (and a preload), and a click handler that does its work in 20 ms.

Every static file has a fixed server-side delay (``DELAYS``), so the *shape* of the numbers is the same on any
machine. ``/api/quote`` is the "backend": two requests at a time, 40 ms each (capacity about 50 per second).

``make_field_samples()`` builds the SYNTHETIC real-user data the lesson uses for the field side of lab versus
field: a made-up mix of mobile and desktop visits, from a seeded random generator, not measured from anyone.
"""

from __future__ import annotations

import json
import random
import socket
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA = Path(__file__).parent / "fe_data"

# Server-side delay in seconds for each path. The page itself is quick; the assets are not.
DELAYS = {
    "/static/app.css": 0.30,
    "/static/vendor.js": 0.10,
    "/static/vendor-chunked.js": 0.10,
    "/static/app.js": 0.10,
    "/static/app-fixed.js": 0.10,
    "/static/analytics.js": 0.05,
    "/static/hero.svg": 0.60,
}

QUOTE_SERVICE_SECONDS = 0.040
QUOTE_CAPACITY = 2

CSS = (
    "body{font-family:sans-serif;margin:8px;max-width:1200px}"
    "h1{margin:8px 0}.hero{width:100%}.hero img{width:100%;height:auto;display:block}"
    "#pay{font-size:20px;padding:10px 24px}p{line-height:1.5}"
)

BUSY = "function busy(ms){var t=performance.now();while(performance.now()-t<ms){}}"

TERMS = "".join(
    f"<p>Clause {n}. SandPay settles approved payments to the merchant account on the next business day, "
    "minus the fee shown in the quote above. Disputes are handled by the settlement desk.</p>"
    for n in range(1, 7)
)


def _padding(kb: int, label: str) -> str:
    return f"/* {label} */\n" + ("/* " + "x" * 61 + " */\n") * (kb * 1024 // 66)


ASSETS = {
    "/static/app.css": ("text/css", CSS + _padding(6, "app.css padding")),
    # A framework-sized bundle with 40 ms of start-up work (under the 50 ms long task line).
    "/static/vendor.js": (
        "application/javascript",
        BUSY + "busy(40);\n" + _padding(240, "vendor.js padding"),
    ),
    # The same work split into 30 ms chunks that yield to the browser in between.
    "/static/vendor-chunked.js": (
        "application/javascript",
        BUSY
        + "(function run(left){busy(30);if(left>1)setTimeout(function(){run(left-1)},0)})(5);\n"
        + _padding(240, "vendor-chunked.js padding"),
    ),
    "/static/analytics.js": ("application/javascript", "window.__analytics=1;\n" + _padding(12, "analytics padding")),
    "/static/hero.svg": (
        "image/svg+xml",
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="300" viewBox="0 0 1200 300">'
        '<defs><linearGradient id="g"><stop offset="0" stop-color="#1b5fa8"/><stop offset="1" stop-color="#2fa37a"/>'
        '</linearGradient></defs><rect width="1200" height="300" fill="url(#g)"/>'
        '<text x="60" y="170" font-size="64" fill="#fff" font-family="sans-serif">SandPay settles tomorrow</text>'
        "</svg>" + _padding(40, "hero padding").replace("/*", "<!--").replace("*/", "-->"),
    ),
}

QUOTE_JS = (
    "fetch('/api/quote').then(function(r){return r.json()}).then(function(q){"
    "document.getElementById('quote').textContent='Fee quote: '+q.fee+' '+q.currency;"
    "performance.mark('quote-shown');});"
)

ASSETS["/static/app.js"] = (
    "application/javascript",
    BUSY
    + "var hero=document.getElementById('hero');var img=new Image();img.src='/static/hero.svg';"
    "img.alt='SandPay settles tomorrow';hero.appendChild(img);\n"
    "setTimeout(function(){busy(200)},300);\n"
    + QUOTE_JS
    + "document.getElementById('pay').addEventListener('click',function(){busy(120);"
    "document.getElementById('pay').textContent='Paid';});\n"
    + _padding(30, "app.js padding"),
)
ASSETS["/static/app-fixed.js"] = (
    "application/javascript",
    BUSY
    + QUOTE_JS
    + "document.getElementById('pay').addEventListener('click',function(){busy(20);"
    "document.getElementById('pay').textContent='Paid';});\n"
    + _padding(30, "app-fixed.js padding"),
)

BODY = (
    "<h1>SandPay checkout</h1>"
    '<div id="hero" class="hero">{hero}</div>'
    '<p id="quote">Fetching your fee quote...</p>'
    + TERMS
    + '<button id="pay">Pay now</button>'
)

SLOW_PAGE = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>SandPay checkout</title>'
    '<link rel="stylesheet" href="/static/app.css">'
    '<script src="/static/vendor.js"></script></head><body>'
    + BODY.format(hero="")
    + '<script src="/static/app.js"></script><script async src="/static/analytics.js"></script></body></html>'
)

FIXED_PAGE = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>SandPay checkout</title>'
    f"<style>{CSS}</style>"
    '<link rel="preload" as="image" href="/static/hero.svg" fetchpriority="high">'
    '<script defer src="/static/vendor-chunked.js"></script></head><body>'
    + BODY.format(
        hero='<img src="/static/hero.svg" width="1200" height="300" fetchpriority="high" alt="SandPay settles tomorrow">'
    )
    + '<script defer src="/static/app-fixed.js"></script></body></html>'
)

PAGES = {"/slow/": SLOW_PAGE, "/fixed/": FIXED_PAGE}


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    quote_gate = threading.Semaphore(QUOTE_CAPACITY)

    def setup(self):
        super().setup()
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def log_message(self, *args):  # keep the test output quiet
        pass

    def _send(self, body: bytes, content_type: str, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in PAGES:
            return self._send(PAGES[path].encode(), "text/html; charset=utf-8")
        if path in ASSETS:
            time.sleep(DELAYS.get(path, 0))
            content_type, body = ASSETS[path]
            return self._send(body.encode(), content_type)
        if path == "/api/quote":
            with self.quote_gate:
                time.sleep(QUOTE_SERVICE_SECONDS)
            return self._send(json.dumps({"fee": "1.20", "currency": "EUR"}).encode(), "application/json")
        return self._send(b"not found", "text/plain", 404)


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128


@contextmanager
def serve(port: int = 0):
    """Start the pages on 127.0.0.1 and yield the base URL (for example ``http://127.0.0.1:41233``)."""
    server = _Server(("127.0.0.1", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def make_field_samples(seed: int = 21, n: int = 400) -> list[dict]:
    """SYNTHETIC real-user visits: ``{"device", "lcp", "inp", "cls"}`` (ms, ms, unitless). ``inp`` is ``None`` for
    a visit with no interaction. Mobile visits are slower and shift more, by construction."""
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        mobile = rng.random() < 0.4
        lcp = rng.lognormvariate(7.75 if mobile else 7.35, 0.42)
        inp = None if rng.random() < 0.2 else rng.lognormvariate(5.2 if mobile else 4.45, 0.55)
        cls = max(0.0, rng.lognormvariate(-2.2 if mobile else -3.6, 0.9) - 0.01)
        rows.append(
            {
                "device": "mobile" if mobile else "desktop",
                "lcp": int(lcp),
                "inp": None if inp is None else int(inp),
                "cls": round(cls, 3),
            }
        )
    return rows


def load_exercise(relative: str):
    import importlib.util

    from load_tools import practice_file

    path = practice_file(relative)
    spec = importlib.util.spec_from_file_location(Path(relative).stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(name: str):
    return json.loads((DATA / name).read_text())
