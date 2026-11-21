"""Solution: the Locust version of the checkout scenario in ``support/tc_checkout.jmx`` - the same scenario in the other tool.

Each virtual merchant signs in once, then loops: list five payments, create one with its own ``Idempotency-Key``,
read it back, think for ``TC_WAIT`` seconds (default 0.2). The four request names match the JMeter sampler names, so
the two tools' results can be put side by side. ``TC_CLIENT=fast`` runs the same scenario on ``FastHttpUser``
(the geventhttpclient based client) instead of ``HttpUser`` (python-requests).
"""

import itertools
import os
import uuid

from locust import FastHttpUser, HttpUser, constant, task

BASE = FastHttpUser if os.environ.get("TC_CLIENT") == "fast" else HttpUser
WAIT = float(os.environ.get("TC_WAIT", "0.2"))
_merchants = itertools.count(1)


class Merchant(BASE):
    wait_time = constant(WAIT)

    def on_start(self):
        n = next(_merchants) % 50 + 1
        r = self.client.post("/auth/token", name="POST /auth/token",
                             json={"client_id": f"merchant-{n}", "client_secret": f"secret-{n}"})
        self.auth = {"Authorization": f"Bearer {r.json()['access_token']}"}

    @task
    def checkout(self):
        self.client.get("/v1/payments?limit=5", name="GET /v1/payments", headers=self.auth)
        r = self.client.post("/v1/payments", name="POST /v1/payments",
                             headers={**self.auth, "Idempotency-Key": str(uuid.uuid4())},
                             json={"amount_minor": 1250, "currency": "EUR"})
        self.client.get(f"/v1/payments/{r.json()['id']}", name="GET /v1/payments/{id}", headers=self.auth)
