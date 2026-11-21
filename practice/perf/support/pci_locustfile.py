"""The Locust user for "Performance testing in CI/CD": a merchant who lists payments and sometimes creates one.

Run by ``pci_fixture.run_summary`` against the practice API. Three of four tasks are reads (stable response times);
one in four is a payment creation with its own ``Idempotency-Key``, which is where the target's injected errors
(``error_rate``) show up. The creations are named ``/v1/payments (create)``; the run summary describes those requests
(Locust keeps one statistics row per name, so a shared name would silently merge or hide one kind).
"""

import itertools

from locust import HttpUser, constant, task

_merchants = itertools.count(1)
_keys = itertools.count(1)
CREATE = "/v1/payments (create)"


class Merchant(HttpUser):
    wait_time = constant(0.02)

    def on_start(self):
        n = next(_merchants) % 50 + 1
        r = self.client.post("/auth/token", json={"client_id": f"merchant-{n}", "client_secret": f"secret-{n}"})
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    @task(3)
    def list_payments(self):
        self.client.get("/v1/payments?limit=10", name="/v1/payments")

    @task(1)
    def create_payment(self):
        self.client.post("/v1/payments", name=CREATE,
                         headers={"Idempotency-Key": f"pci-{next(_keys)}"},
                         json={"amount_minor": 1250, "currency": "EUR"})
