"""A payment load script with the classic mistake: one fixed Idempotency-Key for every request of a user.

Every POST after the first is an idempotent replay: the API answers 201 with the saved response and creates nothing.
Locust sees 201 every time, so the report looks like a perfect run of a very fast endpoint.
"""

import itertools

from locust import HttpUser, constant, task

_merchants = itertools.count(1)


class Merchant(HttpUser):
    wait_time = constant(0.01)

    def on_start(self):
        n = next(_merchants) % 50 + 1
        r = self.client.post("/auth/token", json={"client_id": f"merchant-{n}", "client_secret": f"secret-{n}"},
                             name="/auth/token")
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        self.client.headers["Idempotency-Key"] = "load-test-key"

    @task
    def pay(self):
        self.client.post("/v1/payments", json={"amount_minor": 1250, "currency": "EUR"}, name="POST /v1/payments")
