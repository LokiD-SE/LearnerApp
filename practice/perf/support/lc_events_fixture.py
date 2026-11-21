"""Fixtures for the Locust events and custom clients lesson (tests/locust/test_lc_events_*.py).

1. A loopback-only SandPay *ledger* service that speaks a tiny line protocol over TCP - not HTTP, so Locust's
   ``HttpUser`` cannot test it and a custom client has to report to Locust itself. One request per line, one
   reply per line, ``\\n`` ends each:

   | request                           | reply                                                                 |
   | --------------------------------- | --------------------------------------------------------------------- |
   | ``BALANCE <merchant>``            | ``OK <minor units>``                                                  |
   | ``TRANSFER <from> <to> <amount>`` | transfer call number c: c divisible by 5 -> ``ERR insufficient_funds``;|
   |                                   | otherwise ``OK tx_<n>``. c divisible by 4 also takes 120 ms, the rest 5 ms |
   | anything else                     | ``ERR unknown_command``                                               |

   The outcome comes from a call counter, not a random number, so the counters in ``Ledger.counts`` are exact on
   any machine: ``balances``, ``transfers``, ``declined``, ``approved``, ``connections``.

2. ``write_locustfile(folder, name, exercise_dir)`` writes a small locustfile (below) that imports the
   exercise being tested, so a test can run real Locust on it in a subprocess.
3. ``load_exercise`` and ``serve_gateway`` are re-exported for the tests.

Everything binds to 127.0.0.1 and all data is synthetic.
"""

from __future__ import annotations

import contextlib
import socketserver
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Iterator

from lc_fund_fixture import load_exercise  # noqa: F401 - re-exported for the tests
from lc_valid_fixture import metrics as gateway_metrics  # noqa: F401 - re-exported
from lc_valid_fixture import serve as serve_gateway  # noqa: F401 - re-exported

SLOW_SECONDS = 0.12
FAST_SECONDS = 0.005


class Ledger:
    """A running ledger service: ``host`` is ``"127.0.0.1:<port>"``, ``counts`` its exact counters."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.counts: Counter = Counter()
        self.next_tx = 0
        self.host = ""

    def bump(self, key: str) -> int:
        with self.lock:
            self.counts[key] += 1
            return self.counts[key]


def _handler(ledger: Ledger) -> type[socketserver.StreamRequestHandler]:
    class Handler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            ledger.bump("connections")
            for raw in self.rfile:
                parts = raw.decode().split()
                if len(parts) == 2 and parts[0] == "BALANCE":
                    ledger.bump("balances")
                    time.sleep(0.003)
                    reply = "OK 125000"
                elif len(parts) == 4 and parts[0] == "TRANSFER":
                    c = ledger.bump("transfers")
                    time.sleep(SLOW_SECONDS if c % 4 == 0 else FAST_SECONDS)
                    if c % 5 == 0:
                        ledger.bump("declined")
                        reply = "ERR insufficient_funds"
                    else:
                        with ledger.lock:
                            ledger.next_tx += 1
                            tx = ledger.next_tx
                        ledger.bump("approved")
                        reply = f"OK tx_{tx}"
                else:
                    reply = "ERR unknown_command"
                self.wfile.write(reply.encode() + b"\n")

    return Handler


class _Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128

    def handle_error(self, request, client_address) -> None:
        import sys

        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)):
            return  # a load generator that stops mid-call hangs up; that is not a ledger fault
        super().handle_error(request, client_address)


@contextlib.contextmanager
def serve(host: str = "127.0.0.1", port: int = 0) -> Iterator[Ledger]:
    """Serves the ledger on loopback in a background thread; yields the ``Ledger`` (its ``host`` and counters)."""
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("the practice ledger only binds to the loopback interface")
    ledger = Ledger()
    server = _Server((host, port), _handler(ledger))
    ledger.host = f"{host}:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield ledger
    finally:
        server.shutdown()
        server.server_close()


LOCUSTFILES = {
    # Charges against the legacy gateway (always HTTP 200; every 4th charge declined, every 7th an HTML page) and
    # installs the learner's request audit. Settings come from environment variables.
    "audit": '''
import itertools
import os
import sys
from json import JSONDecodeError

sys.path.insert(0, {exercise_dir!r})
from lc_events_audit import RequestAudit, install

from locust import HttpUser, constant, events, task

install(events, RequestAudit(slow_ms=float(os.environ["LC_EVENTS_SLOW_MS"])), os.environ["LC_EVENTS_OUT"])
_numbers = itertools.count(1)


class Merchant(HttpUser):
    wait_time = constant(0)

    def on_start(self):
        n = next(_numbers)
        self.merchant = f"merchant-{{n}}"
        self.client.post("/gateway/login", json={{"username": self.merchant, "password": f"secret-{{n}}"}},
                         name="login", context={{"merchant": self.merchant}})

    @task
    def charge(self):
        with self.client.post("/gateway/charges", json={{"amount_minor": 1250, "currency": "EUR"}}, name="charge",
                              catch_response=True, context={{"merchant": self.merchant}}) as r:
            try:
                body = r.json()
            except JSONDecodeError:
                r.failure("not JSON: HTTP 200 text/html")
                return
            if body.get("status") == "declined":
                r.failure(f"declined: {{body.get('decline_code')}}")
''',
    # The same charges, with the learner's quality gate. The limit comes from LC_EVENTS_MAX_FAIL.
    "gate": '''
import itertools
import os
import sys
from json import JSONDecodeError

sys.path.insert(0, {exercise_dir!r})
from lc_events_gate import install

from locust import HttpUser, constant, events, task

install(events, max_fail_ratio=float(os.environ["LC_EVENTS_MAX_FAIL"]), p95_ms=60_000)
_numbers = itertools.count(1)


class Merchant(HttpUser):
    wait_time = constant(0)

    def on_start(self):
        n = next(_numbers)
        self.client.post("/gateway/login", json={{"username": f"merchant-{{n}}", "password": f"secret-{{n}}"}},
                         name="login")

    @task
    def charge(self):
        with self.client.post("/gateway/charges", json={{"amount_minor": 1250, "currency": "EUR"}}, name="charge",
                              catch_response=True) as r:
            try:
                body = r.json()
            except JSONDecodeError:
                r.failure("not JSON: HTTP 200 text/html")
                return
            if body.get("status") == "declined":
                r.failure(f"declined: {{body.get('decline_code')}}")
''',
}


def write_locustfile(folder: Path, name: str, exercise_dir: Path) -> Path:
    path = folder / f"{name}_locustfile.py"
    path.write_text(LOCUSTFILES[name].lstrip().format(exercise_dir=str(exercise_dir)))
    return path
