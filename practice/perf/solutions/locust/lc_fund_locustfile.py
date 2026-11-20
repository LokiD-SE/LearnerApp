"""Your first SandPay locustfile - reference solution.

A merchant dashboard user: it logs in once, then mostly lists recent payments and sometimes opens one.

    .venv/bin/locust -f solutions/locust/lc_fund_locustfile.py --headless -u 4 -r 4 -t 10s \\
        --host http://127.0.0.1:8090

merchant-1 owns payments pay_100001 .. pay_100250 in the practice API (support/sandpay_target.py).
"""

import random

from locust import HttpUser, constant_throughput, task


class MerchantUser(HttpUser):
    host = "http://127.0.0.1:8090"  # the default; --host on the command line overrides it
    wait_time = constant_throughput(2)  # at most 2 task runs per second per user

    def on_start(self):
        # Runs once per simulated user, before its first task - not counted as a task.
        r = self.client.post("/auth/token", json={"client_id": "merchant-1", "client_secret": "secret-1"})
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    @task(3)
    def list_payments(self):
        self.client.get("/v1/payments?limit=10", name="/v1/payments")

    @task(1)
    def view_payment(self):
        payment_id = f"pay_{random.randint(100001, 100250)}"
        self.client.get(f"/v1/payments/{payment_id}", name="/v1/payments/[id]")
