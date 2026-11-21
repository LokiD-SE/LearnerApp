"""A locustfile that fails the pipeline: the exit code of a distributed run, decided on the master.

Locust exits with 1 when any request failed (``--exit-code-on-error``, default 1) and 0 otherwise. A pipeline
usually wants its own rule: too many failures OR a slow 95th percentile. The Locust docs ("Controlling the exit
code of the Locust process") do it in a ``quitting`` listener that sets ``environment.process_exit_code``.

Distributed runs add a trap. The listener runs in EVERY process - the master and each worker - but only the
master sees the merged statistics (a worker resets its own after each report), and the pipeline reads the
master's exit code. Gate on the master, and leave the workers alone.

Thresholds come from the environment, so the same file serves every run:
LC_GATE_MAX_FAIL_RATIO (default 0.01) and LC_GATE_P95_MS (default 800).

Implement ``verdict`` and the listener; tests/locust/test_lc_dist_gate.py runs real distributed clusters.
"""

import logging
import os
import uuid

from locust import HttpUser, constant, events, task
from locust.runners import WorkerRunner


class Prober(HttpUser):
    wait_time = constant(0.05)

    def on_start(self):
        r = self.client.post("/auth/token", json={"client_id": "merchant-1", "client_secret": "secret-1"})
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    @task(3)
    def health(self):
        self.client.get("/health")

    @task(2)
    def create_payment(self):
        # fails with a 500 for the share of requests the target is configured to break
        self.client.post("/v1/payments", json={"amount_minor": 1250, "currency": "EUR"},
                         headers={"Idempotency-Key": str(uuid.uuid4())})

    @task(1)
    def settlement(self):
        # ten times the service time, so a p95 threshold has something to bite on
        self.client.get("/v1/reports/settlement")


def verdict(fail_ratio: float, p95_ms: float, max_fail_ratio: float, max_p95_ms: float) -> tuple[int, list[str]]:
    reasons = []
    if fail_ratio > max_fail_ratio:
        reasons.append(f"failure ratio {fail_ratio:.4f} > {max_fail_ratio}")
    if p95_ms > max_p95_ms:
        reasons.append(f"95th percentile {p95_ms} ms > {max_p95_ms} ms")
    return (1 if reasons else 0), reasons


@events.quitting.add_listener
def gate(environment, **_):
    if isinstance(environment.runner, WorkerRunner):
        return
    total = environment.stats.total
    code, reasons = verdict(total.fail_ratio, total.get_response_time_percentile(0.95),
                            float(os.environ.get("LC_GATE_MAX_FAIL_RATIO", "0.01")),
                            float(os.environ.get("LC_GATE_P95_MS", "800")))
    for r in reasons:
        logging.error("gate failed: %s", r)
    environment.process_exit_code = code
