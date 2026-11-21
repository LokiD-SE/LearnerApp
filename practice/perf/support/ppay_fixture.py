"""Fixtures for the lesson "Performance testing payment systems" (exercises under analysis/ppay_*).

All of it talks to the loopback practice API in ``sandpay_target.py`` (``POST /v1/payments`` with an ``Idempotency-Key``,
the per-client limit on ``POST /auth/token``, ``GET /metrics`` with ``payments_created`` and ``idempotent_replays``).

- ``load_exercise(relative)`` imports an exercise module from its file.
- ``call(base, method, path, body, headers, timeout)`` one HTTP call; returns ``(status, headers, body)`` and raises
  ``TimeoutError`` when the answer does not arrive in ``timeout`` seconds.
- ``token(base, n)``, ``metrics(base)``, ``make_send(base, token)`` (the ``send(key)`` function ``submit_payment`` wants).
- ``probe_rows(base, token, n, key_mode)`` sends ``n`` payments one after another with one fixed key or a fresh key each
  and returns triage rows.
- ``timeout_scenario(wait_s, same_key)`` is the experiment of the lesson: the first request of a payment times out on the
  client while the API carries it out, then the script retries after ``wait_s`` seconds with the same key or a new one.
  It returns ``(ledger, metrics)``.
- ``run_pay_locust(base, out_dir, users, run_time)`` runs ``ppay_user_locustfile.py`` with the exercise (or solution)
  retry rules and returns ``(ledger, locust_stats)``.
"""

from __future__ import annotations

import http.client
import importlib.util
import json
import os
import socket
import uuid
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BODY = {"amount_minor": 1250, "currency": "EUR"}


def load_exercise(relative: str) -> ModuleType:
    from load_tools import practice_file

    path = practice_file(relative)
    spec = importlib.util.spec_from_file_location(Path(relative).stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _hostport(base: str) -> tuple[str, int]:
    host, port = base.removeprefix("http://").split(":")
    return host, int(port)


def call(base, method, path, body=None, headers=None, timeout=5.0):
    host, port = _hostport(base)
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request(method, path, json.dumps(body) if body is not None else None, headers or {})
        r = conn.getresponse()
        return r.status, dict(r.getheaders()), json.loads(r.read() or b"{}")
    except (socket.timeout, TimeoutError):
        raise TimeoutError(f"no answer from {path} in {timeout} s") from None
    finally:
        conn.close()


def token(base: str, n: int = 1) -> str:
    return call(base, "POST", "/auth/token", {"client_id": f"merchant-{n}", "client_secret": f"secret-{n}"})[2]["access_token"]


def metrics(base: str) -> dict:
    return call(base, "GET", "/metrics")[2]


def make_send(base: str, tok: str, timeout: float = 5.0):
    def send(key):
        status, headers, _ = call(base, "POST", "/v1/payments", BODY,
                                  {"Authorization": f"Bearer {tok}", "Idempotency-Key": key}, timeout)
        return status, headers

    return send


def probe_rows(base: str, tok: str, n: int, key_mode: str) -> list[dict]:
    send = make_send(base, tok)
    fixed = str(uuid.uuid4())
    rows = []
    for _ in range(n):
        status, headers = send(fixed if key_mode == "fixed" else str(uuid.uuid4()))
        rows.append({"status": status, "headers": headers})
    return rows


def timeout_scenario(wait_s: float, same_key: bool, base: str | None = None):
    """The first request times out on the client (40 ms) while the API needs 200 ms to carry it out."""
    import time

    from sandpay_target import TargetConfig, serve

    def run(url):
        tok = token(url)
        key = "pay-key-1"
        attempts = []
        try:
            call(url, "POST", "/v1/payments", BODY, {"Authorization": f"Bearer {tok}", "Idempotency-Key": key}, 0.04)
            attempts.append({"key": key, "status": 201, "replayed": False})
        except TimeoutError:
            attempts.append({"key": key, "status": None, "replayed": False})
        time.sleep(wait_s)
        retry_key = key if same_key else "pay-key-2"
        status, headers, _ = call(url, "POST", "/v1/payments", BODY,
                                  {"Authorization": f"Bearer {tok}", "Idempotency-Key": retry_key})
        attempts.append({"key": retry_key, "status": status,
                         "replayed": headers.get("Idempotent-Replayed") == "true"})
        time.sleep(0.3)  # let the first request finish on the API side before the counters are read
        return [{"logical": "pay-1", "attempts": attempts, "outcome": "ok"}], metrics(url)

    if base:
        return run(base)
    with serve(TargetConfig(latency_ms=100, capacity=8)) as url:
        return run(url)


def run_pay_locust(base: str, out_dir: Path, users: int = 6, run_time: str = "4s"):
    from load_tools import read_locust_stats, run_locust

    out_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = out_dir / "ledger.jsonl"
    ledger_path.unlink(missing_ok=True)
    target = os.environ.get("PERF_TARGET", "exercises")
    saved = {k: os.environ.get(k) for k in ("PPAY_DIR", "PPAY_LEDGER")}
    os.environ["PPAY_DIR"] = str(ROOT / target / "analysis")
    os.environ["PPAY_LEDGER"] = str(ledger_path)
    try:
        prefix = run_locust(HERE / "ppay_user_locustfile.py", base, users, users, run_time, out_dir)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    ledger = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
    return ledger, read_locust_stats(prefix)
