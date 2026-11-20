"""Checks the shared practice tooling (not a learner exercise; verify.py skips tests/support):
the SandPay target behaves as documented, and JMeter and Locust can load it headless."""

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from load_tools import jmeter_home, read_jtl, read_locust_stats, run_jmeter, run_locust
from sandpay_target import TargetConfig, serve

FIX = Path(__file__).parent / "fixtures"


def req(base, method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(base + path, data=data, method=method,
                               headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, dict(resp.headers), json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), json.loads(e.read())


def token(base, n=1):
    return req(base, "POST", "/auth/token", {"client_id": f"merchant-{n}", "client_secret": f"secret-{n}"})[2]["access_token"]


def test_auth_pagination_idempotency():
    with serve(TargetConfig(latency_ms=1)) as base:
        t = {"Authorization": f"Bearer {token(base)}"}
        assert req(base, "GET", "/v1/payments")[0] == 401
        s, _, page = req(base, "GET", "/v1/payments?limit=5", headers=t)
        assert s == 200 and len(page["data"]) == 5 and page["has_more"]
        s, _, nxt = req(base, "GET", f"/v1/payments?limit=5&starting_after={page['data'][-1]['id']}", headers=t)
        assert nxt["data"][0]["id"] != page["data"][-1]["id"]
        body = {"amount_minor": 1250, "currency": "EUR"}
        assert req(base, "POST", "/v1/payments", body, t)[0] == 400
        s1, _, p1 = req(base, "POST", "/v1/payments", body, {**t, "Idempotency-Key": "k-1"})
        s2, h2, p2 = req(base, "POST", "/v1/payments", body, {**t, "Idempotency-Key": "k-1"})
        assert (s1, s2) == (201, 201) and p1 == p2 and h2.get("Idempotent-Replayed") == "true"
        m = req(base, "GET", "/metrics")[2]
        assert (m["payments_created"], m["idempotent_replays"]) == (1, 1)


def test_capacity_queues_and_sheds():
    with serve(TargetConfig(latency_ms=50, capacity=2, queue_limit=2)) as base:
        t = {"Authorization": f"Bearer {token(base)}"}
        with ThreadPoolExecutor(12) as pool:
            statuses = list(pool.map(lambda _: req(base, "GET", "/v1/payments?limit=1", headers=t)[0], range(12)))
        assert 503 in statuses and 200 in statuses
        m = req(base, "GET", "/metrics")[2]
        assert m["max_in_flight"] <= 2


def test_rate_limit():
    with serve(TargetConfig(latency_ms=0, rate_limit_rps=3)) as base:
        codes = [req(base, "POST", "/auth/token", {"client_id": "merchant-2", "client_secret": "secret-2"})[0]
                 for _ in range(5)]
        assert codes.count(429) >= 1


def test_refuses_non_loopback():
    with pytest.raises(ValueError):
        with serve(host="0.0.0.0"):
            pass


@pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")
def test_jmeter_runs_headless(tmp_path):
    with serve(TargetConfig(latency_ms=1)) as base:
        port = base.rsplit(":", 1)[1]
        rows = read_jtl(run_jmeter(FIX / "smoke.jmx", {"port": port, "threads": 2, "loops": 3}, tmp_path))
    assert len(rows) == 6 and {r["responseCode"] for r in rows} == {"200"}


def test_locust_runs_headless(tmp_path):
    with serve(TargetConfig(latency_ms=1)) as base:
        prefix = run_locust(FIX / "smoke_locustfile.py", base, users=2, spawn_rate=2, run_time="2s", out_dir=tmp_path)
    stats = read_locust_stats(prefix)  # final totals; _stats.csv may still be a second behind
    assert stats["/health"]["num_requests"] > 0 and stats["/health"]["num_failures"] == 0
