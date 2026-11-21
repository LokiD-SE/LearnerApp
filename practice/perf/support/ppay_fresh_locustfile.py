"""The same payment load with a fresh Idempotency-Key (a random UUID, version 4) for every logical payment."""

import itertools
import uuid

from locust import HttpUser, constant, task

_merchants = itertools.count(1)


class Merchant(HttpUser):
    wait_time = constant(0.01)

    def on_start(self):
        n = next(_merchants) % 50 + 1
        r = self.client.post("/auth/token", json={"client_id": f"merchant-{n}", "client_secret": f"secret-{n}"},
                             name="/auth/token")
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    @task
    def pay(self):
        self.client.post("/v1/payments", json={"amount_minor": 1250, "currency": "EUR"},
                         headers={"Idempotency-Key": str(uuid.uuid4())}, name="POST /v1/payments")
