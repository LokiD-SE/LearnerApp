"""A payment workload with a share of slow settlement reports in the mix.

``PPAY_REPORT_WEIGHT`` (default 0) is the weight of ``GET /v1/reports/settlement`` against a weight of 19 for
``POST /v1/payments``; 1 means one request in twenty is a report. Every user logs in once and sends a fresh
Idempotency-Key for every payment. No think time, so the run shows the most the API can carry (a closed loop).
"""

import itertools
import os
import uuid

from locust import HttpUser, constant, task

_merchants = itertools.count(1)
REPORT = int(os.environ.get("PPAY_REPORT_WEIGHT", "0"))


class Merchant(HttpUser):
    wait_time = constant(0)

    def on_start(self):
        n = next(_merchants) % 50 + 1
        r = self.client.post("/auth/token", json={"client_id": f"merchant-{n}", "client_secret": f"secret-{n}"},
                             name="/auth/token")
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    def pay(self):
        self.client.post("/v1/payments", json={"amount_minor": 1250, "currency": "EUR"},
                         headers={"Idempotency-Key": str(uuid.uuid4())}, name="POST /v1/payments")

    def report(self):
        self.client.get("/v1/reports/settlement", name="GET /v1/reports/settlement")

    tasks = {pay: 19, report: REPORT} if REPORT else {pay: 19}
