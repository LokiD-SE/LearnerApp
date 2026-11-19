"""SandPay practice API - a local load-test target for the performance testing track (Track K).

It runs on the loopback interface only, so JMeter and Locust exercises never load anybody else's system.
SandPay is fictional; all data is synthetic. Behaviour is configurable so a lesson can show what saturation,
errors and rate limiting look like from the load generator's side:

- ``latency_ms`` / ``jitter_ms``: service time per request (seeded random jitter, so runs are repeatable).
- ``capacity``: how many requests are served at once; more wait in a queue, so latency grows with load
  (a simple model of a saturated worker pool - Little's law in action).
- ``queue_limit``: requests beyond capacity + queue_limit get ``503`` with ``Retry-After: 1``.
- ``error_rate``: fraction of payment creations that fail with ``500`` (seeded).
- ``rate_limit_rps``: per-client token requests per second before ``429`` (0 = off).

Endpoints (JSON):

| method | path                         | notes                                                                 |
| ------ | ---------------------------- | --------------------------------------------------------------------- |
| GET    | /health                      | no auth, no service time                                              |
| POST   | /auth/token                  | ``{"client_id", "client_secret"}`` -> ``{"access_token", "expires_in"}`` |
| GET    | /v1/payments                 | ``?limit=1..100&starting_after=<id>`` cursor pagination                 |
| GET    | /v1/payments/<id>            | ``404`` if unknown                                                     |
| POST   | /v1/payments                 | ``Idempotency-Key`` header required; same key -> same response          |
| GET    | /v1/reports/settlement       | slow report: 10x the service time                                      |
| GET    | /metrics                     | server-side counters (requests, in_flight, max_in_flight, statuses)   |
| POST   | /metrics/reset               | zero the counters between runs                                         |

Synthetic clients: ``merchant-1`` .. ``merchant-50``, secret ``secret-<n>`` (for example ``merchant-7`` /
``secret-7``).

Run it by hand: ``.venv/bin/python support/sandpay_target.py --port 8090 --latency-ms 20 --capacity 8``
In tests:       ``with serve(TargetConfig(latency_ms=5)) as base_url: ...``
"""

from __future__ import annotations

import argparse
import contextlib
import json
import random
import secrets
import threading
import time
import urllib.parse
from collections import Counter
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator

LOOPBACK = ("127.0.0.1", "localhost", "::1")
CURRENCIES = ("EUR", "GBP", "USD")


@dataclass
class TargetConfig:
    latency_ms: float = 10.0
    jitter_ms: float = 0.0
    capacity: int = 16
    queue_limit: int = 1000
    error_rate: float = 0.0
    rate_limit_rps: float = 0.0
    seed: int = 7
    payments: int = 250  # seeded payments per merchant-1 .. merchant-3


@dataclass
class State:
    config: TargetConfig
    rng: random.Random = field(init=False)
    lock: threading.Lock = field(default_factory=threading.Lock)
    workers: threading.Semaphore = field(init=False)
    waiting: int = 0
    in_flight: int = 0
    max_in_flight: int = 0
    statuses: Counter = field(default_factory=Counter)
    routes: Counter = field(default_factory=Counter)
    tokens: dict[str, str] = field(default_factory=dict)  # token -> client_id
    token_times: dict[str, list[float]] = field(default_factory=dict)
    payments: dict[str, dict] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    idempotency: dict[tuple[str, str], tuple[int, dict]] = field(default_factory=dict)
    next_id: int = 100000

    def __post_init__(self) -> None:
        self.rng = random.Random(self.config.seed)
        self.workers = threading.Semaphore(self.config.capacity)
        for m in (1, 2, 3):
            for _ in range(self.config.payments):
                self._add_payment(f"merchant-{m}", self.rng.randint(100, 50000), self.rng.choice(CURRENCIES),
                                  self.rng.choice(("captured", "captured", "captured", "refunded", "failed")))

    def _add_payment(self, client: str, amount: int, currency: str, status: str = "captured") -> dict:
        self.next_id += 1
        pid = f"pay_{self.next_id}"
        p = {"id": pid, "merchant": client, "amount_minor": amount, "currency": currency, "status": status}
        self.payments[pid] = p
        self.order.append(pid)
        return p


class Reply(Exception):
    def __init__(self, status: int, body: dict, headers: list[tuple[str, str]] | None = None):
        self.status, self.body, self.headers = status, body, headers or []


def _service(state: State, factor: float = 1.0) -> None:
    c = state.config
    with state.lock:
        jitter = state.rng.uniform(-c.jitter_ms, c.jitter_ms) if c.jitter_ms else 0.0
    time.sleep(max(0.0, (c.latency_ms + jitter) * factor) / 1000)


def _client(state: State, headers: dict[str, str]) -> str:
    auth = headers.get("authorization", "")
    client = state.tokens.get(auth[7:]) if auth.startswith("Bearer ") else None
    if client is None:
        raise Reply(401, {"error": "missing or unknown bearer token"})
    return client


def handle(state: State, method: str, path: str, query: dict[str, str], headers: dict[str, str], body: bytes):
    if path == "/health":
        return 200, {"status": "ok"}, []
    if path == "/metrics" and method == "GET":
        with state.lock:
            return 200, {"in_flight": state.in_flight, "max_in_flight": state.max_in_flight,
                         "waiting": state.waiting, "requests": sum(state.statuses.values()),
                         "statuses": {str(k): v for k, v in sorted(state.statuses.items())},
                         "routes": dict(sorted(state.routes.items()))}, []
    if path == "/metrics/reset" and method == "POST":
        with state.lock:
            state.statuses.clear()
            state.routes.clear()
            state.max_in_flight = state.in_flight
        return 200, {"status": "reset"}, []

    c = state.config
    with state.lock:
        if state.waiting + state.in_flight >= c.capacity + c.queue_limit:
            raise Reply(503, {"error": "server busy"}, [("Retry-After", "1")])
        state.waiting += 1
    state.workers.acquire()
    with state.lock:
        state.waiting -= 1
        state.in_flight += 1
        state.max_in_flight = max(state.max_in_flight, state.in_flight)
    try:
        return _route(state, method, path, query, headers, body)
    finally:
        with state.lock:
            state.in_flight -= 1
        state.workers.release()


def _route(state: State, method: str, path: str, query: dict[str, str], headers: dict[str, str], body: bytes):
    c = state.config
    try:
        data = json.loads(body) if body else {}
    except json.JSONDecodeError:
        raise Reply(400, {"error": "body is not valid JSON"})
    if path == "/auth/token" and method == "POST":
        _service(state)
        cid, secret = str(data.get("client_id", "")), str(data.get("client_secret", ""))
        n = cid.removeprefix("merchant-")
        if not (n.isdigit() and 1 <= int(n) <= 50 and secret == f"secret-{n}"):
            raise Reply(401, {"error": "invalid client credentials"})
        if c.rate_limit_rps:
            now = time.monotonic()
            with state.lock:
                recent = [t for t in state.token_times.get(cid, []) if now - t < 1.0]
                if len(recent) >= c.rate_limit_rps:
                    raise Reply(429, {"error": "rate limit exceeded"}, [("Retry-After", "1")])
                state.token_times[cid] = recent + [now]
        token = secrets.token_urlsafe(18)
        with state.lock:
            state.tokens[token] = cid
        return 200, {"access_token": token, "token_type": "Bearer", "expires_in": 3600}, []
    if path == "/v1/payments" and method == "GET":
        client = _client(state, headers)
        _service(state)
        try:
            limit = int(query.get("limit", "10"))
        except ValueError:
            raise Reply(400, {"error": "limit must be an integer"})
        if not 1 <= limit <= 100:
            raise Reply(400, {"error": "limit must be between 1 and 100"})
        mine = [state.payments[p] for p in state.order if state.payments[p]["merchant"] == client]
        after = query.get("starting_after")
        if after:
            ids = [p["id"] for p in mine]
            if after not in ids:
                raise Reply(400, {"error": "unknown starting_after"})
            mine = mine[ids.index(after) + 1:]
        page = mine[:limit]
        return 200, {"data": page, "has_more": len(mine) > limit}, []
    if path.startswith("/v1/payments/") and method == "GET":
        client = _client(state, headers)
        _service(state)
        p = state.payments.get(path.rsplit("/", 1)[-1])
        if p is None or p["merchant"] != client:
            raise Reply(404, {"error": "payment not found"})
        return 200, p, []
    if path == "/v1/payments" and method == "POST":
        client = _client(state, headers)
        key = headers.get("idempotency-key")
        if not key:
            raise Reply(400, {"error": "Idempotency-Key header is required"})
        with state.lock:
            seen = state.idempotency.get((client, key))
        if seen:
            return seen[0], seen[1], [("Idempotent-Replayed", "true")]
        _service(state, 2.0)
        amount, currency = data.get("amount_minor"), data.get("currency")
        if not isinstance(amount, int) or amount <= 0 or currency not in CURRENCIES:
            raise Reply(422, {"error": "amount_minor must be a positive integer and currency one of EUR, GBP, USD"})
        with state.lock:
            failed = c.error_rate and state.rng.random() < c.error_rate
        if failed:
            raise Reply(500, {"error": "acquirer timeout (simulated)"})
        with state.lock:
            p = state._add_payment(client, amount, currency)
            state.idempotency[(client, key)] = (201, p)
        return 201, p, []
    if path == "/v1/reports/settlement" and method == "GET":
        _client(state, headers)
        _service(state, 10.0)
        return 200, {"report": "settlement", "rows": 42}, []
    raise Reply(404, {"error": "not found"})


def _handler_for(state: State) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        # Headers and body go out as separate writes; without this, Nagle + delayed ACK add ~40 ms per keep-alive request.
        disable_nagle_algorithm = True

        def _serve(self) -> None:
            split = urllib.parse.urlsplit(self.path)
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            query = {k: v[0] for k, v in urllib.parse.parse_qs(split.query).items()}
            headers = {k.lower(): v for k, v in self.headers.items()}
            route = split.path if not split.path.startswith("/v1/payments/") else "/v1/payments/{id}"
            try:
                status, payload, extra = handle(state, self.command, split.path, query, headers, body)
            except Reply as r:
                status, payload, extra = r.status, r.body, r.headers
            data = json.dumps(payload).encode()
            if not split.path.startswith("/metrics"):
                with state.lock:
                    state.statuses[status] += 1
                    state.routes[f"{self.command} {route}"] += 1
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            for k, v in extra:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = _serve

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return Handler


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 1024

    def handle_error(self, request: Any, client_address: Any) -> None:
        # A load generator that stops mid-request closes its sockets; that is not a server fault.
        import sys
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)


@contextlib.contextmanager
def serve(config: TargetConfig | None = None, host: str = "127.0.0.1", port: int = 0) -> Iterator[str]:
    """Serves the target on loopback in a background thread; yields the base URL."""
    if host not in LOOPBACK:
        raise ValueError("the practice target only binds to the loopback interface")
    state = State(config or TargetConfig())
    server = _Server((host, port), _handler_for(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def main() -> None:
    p = argparse.ArgumentParser(description="SandPay practice API (loopback only) for load tests")
    p.add_argument("--port", type=int, default=8090)
    p.add_argument("--latency-ms", type=float, default=10.0)
    p.add_argument("--jitter-ms", type=float, default=0.0)
    p.add_argument("--capacity", type=int, default=16)
    p.add_argument("--queue-limit", type=int, default=1000)
    p.add_argument("--error-rate", type=float, default=0.0)
    p.add_argument("--rate-limit-rps", type=float, default=0.0)
    p.add_argument("--seed", type=int, default=7)
    a = p.parse_args()
    cfg = TargetConfig(a.latency_ms, a.jitter_ms, a.capacity, a.queue_limit, a.error_rate, a.rate_limit_rps, a.seed)
    with serve(cfg, port=a.port) as url:
        print(f"SandPay practice API on {url} ({cfg}) - Ctrl+C to stop", flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
