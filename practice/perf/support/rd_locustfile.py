"""The Locust user for the noisy-runs demonstration: eight merchants listing payments in a loop.

Run by ``rd_capture.py`` against the practice API (``latency_ms`` and ``capacity`` are set by the caller). With more
users than the target's capacity, requests queue, so the response time depends on timing - exactly the kind of
run that varies from one execution to the next.
"""

import itertools

from locust import HttpUser, constant, task

_merchants = itertools.count(1)


class Merchant(HttpUser):
    wait_time = constant(0.02)

    def on_start(self):
        n = next(_merchants) % 50 + 1
        r = self.client.post("/auth/token", json={"client_id": f"merchant-{n}", "client_secret": f"secret-{n}"})
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    @task
    def list_payments(self):
        self.client.get("/v1/payments?limit=10", name="/v1/payments")
