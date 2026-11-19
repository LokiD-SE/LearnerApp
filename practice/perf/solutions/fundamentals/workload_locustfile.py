"""A Locust user built from the SandPay workload model - reference solution.

The model (from the lesson's access log, merchant calls after login, rounded to integer weights):

    GET  /v1/payments            55
    GET  /v1/payments/{id}       27
    POST /v1/payments            15
    GET  /v1/reports/settlement   3

Each simulated merchant logs in once (on_start), then picks one task per iteration with these weights.
Requests are named after the model's transactions so Locust's statistics line up with the model.

Run against the practice API (see support/sandpay_target.py):
    .venv/bin/locust -f solutions/fundamentals/workload_locustfile.py --headless -u 10 -r 10 -t 30s \\
        --host http://127.0.0.1:8090
"""

import itertools
import random
import uuid

from locust import HttpUser, constant, task

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

    @task(MODEL["GET /v1/payments"])
    def list_payments(self):
        self.client.get("/v1/payments?limit=20", name="GET /v1/payments")

    @task(MODEL["GET /v1/payments/{id}"])
    def get_payment(self):
        self.client.get(f"/v1/payments/{random.choice(self.payment_ids)}", name="GET /v1/payments/{id}")

    @task(MODEL["POST /v1/payments"])
    def create_payment(self):
        self.client.post("/v1/payments", json={"amount_minor": random.randint(100, 50000), "currency": "EUR"},
                         headers={"Idempotency-Key": str(uuid.uuid4())}, name="POST /v1/payments")

    @task(MODEL["GET /v1/reports/settlement"])
    def settlement_report(self):
        self.client.get("/v1/reports/settlement", name="GET /v1/reports/settlement")
