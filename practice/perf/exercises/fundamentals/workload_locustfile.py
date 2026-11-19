"""A Locust user built from the SandPay workload model - EXERCISE.

The model (from the lesson's access log, merchant calls after login, rounded to integer weights):

    GET  /v1/payments            55
    GET  /v1/payments/{id}       27
    POST /v1/payments            15
    GET  /v1/reports/settlement   3

Each simulated merchant logs in once (on_start - already written for you), then picks one task per
iteration with these weights.

TODO - add four @task methods to MerchantUser, one per model transaction:
- give each the model's weight: @task(MODEL["GET /v1/payments"]) and so on;
- name every request after its transaction with name="..." so Locust's statistics line up with the model -
  in particular, all GET-by-id requests must share the one name "GET /v1/payments/{id}";
- GET /v1/payments?limit=20 for the list; GET /v1/payments/<a random id from self.payment_ids>;
- POST /v1/payments with JSON {"amount_minor": <positive int>, "currency": "EUR"} and a fresh
  Idempotency-Key header (str(uuid.uuid4())) - the practice API requires one;
- GET /v1/reports/settlement.

Run: .venv/bin/python -m pytest tests/fundamentals/test_workload_locustfile.py
"""

import itertools
import random  # noqa: F401 - you will need it
import uuid  # noqa: F401 - you will need it

from locust import HttpUser, constant

MODEL = {
    "GET /v1/payments": 55,
    "GET /v1/payments/{id}": 27,
    "POST /v1/payments": 15,
    "GET /v1/reports/settlement": 3,
}
_merchant_numbers = itertools.count(1)


class MerchantUser(HttpUser):
    # The test measures the mix, so iterations run back to back. For a real test, pace users from the model
    # instead - for example wait_time = poisson(rate) or constant_throughput(rate) (see the lesson).
    wait_time = constant(0)

    def on_start(self):
        n = (next(_merchant_numbers) - 1) % 3 + 1  # merchant-1..3 have seeded payments in the practice API
        r = self.client.post("/auth/token", json={"client_id": f"merchant-{n}", "client_secret": f"secret-{n}"},
                             name="POST /auth/token")
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        page = self.client.get("/v1/payments?limit=100", name="setup: payment ids").json()
        self.payment_ids = [p["id"] for p in page["data"]]

    # TODO: the four weighted, named tasks.
