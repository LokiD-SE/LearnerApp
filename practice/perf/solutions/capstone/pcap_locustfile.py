"""The settlement-day workload for the SandPay API as a Locust script - reference solution.

One virtual merchant (user) signs in once, reads its first page of payments once (the setup step, to learn some
payment ids), then repeats one transaction at a time, picked by weight, with a think time between them:

    POST /v1/payments              weight 8   (40 %)
    GET  /v1/payments              weight 6   (30 %)
    GET  /v1/payments/{id}         weight 5   (25 %)
    GET  /v1/reports/settlement    weight 1   ( 5 %)

Every transaction has a fixed request name, so Locust groups ``/v1/payments/pay_100123`` and
``/v1/payments/pay_100124`` into one row. ``PCAP_THINK`` (seconds, default 0.3) sets the think time.
The practice API only seeds payments for merchant-1 .. merchant-3, so users share those three merchants.
"""

import itertools
import os
import random
import uuid

from locust import HttpUser, constant, task

THINK = float(os.environ.get("PCAP_THINK", "0.3"))
_merchants = itertools.count(0)


class Merchant(HttpUser):
    wait_time = constant(THINK)

    def on_start(self):
        n = next(_merchants) % 3 + 1
        r = self.client.post("/auth/token", json={"client_id": f"merchant-{n}", "client_secret": f"secret-{n}"},
                             name="POST /auth/token")
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        page = self.client.get("/v1/payments", params={"limit": 50}, name="setup: GET /v1/payments")
        self.payment_ids = [p["id"] for p in page.json()["data"]]

    @task(8)
    def create_payment(self):
        self.client.post("/v1/payments", json={"amount_minor": random.randint(100, 5000), "currency": "EUR"},
                         headers={"Idempotency-Key": str(uuid.uuid4())}, name="POST /v1/payments")

    @task(6)
    def list_payments(self):
        self.client.get("/v1/payments", params={"limit": 10}, name="GET /v1/payments")

    @task(5)
    def read_payment(self):
        self.client.get(f"/v1/payments/{random.choice(self.payment_ids)}", name="GET /v1/payments/{id}")

    @task(1)
    def settlement_report(self):
        self.client.get("/v1/reports/settlement", name="GET /v1/reports/settlement")
