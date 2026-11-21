"""The SandPay merchant console as nested TaskSets - reference solution.

One simulated merchant:

1. User.on_start: logs in once (merchant-1, which has seeded payments to read) and keeps the bearer token on
   self.client.headers. A TaskSet's self.client is the same session, so the token is sent from inside the TaskSet too.
2. Top level (tasks = {...}): Browse with weight 3, run_settlement_report with weight 1 - a merchant is in the
   payments screen three times as often as they open the slow report.
3. Browse (a TaskSet): on_start sends "GET /v1/payments (open)" when the user enters the screen. Inside it:
   list_payments (weight 5), view_payment (weight 3, one name for all ids) and leave (weight 2), which calls
   self.interrupt() - without that call the user would stay in Browse for the whole test.

Run by hand: .venv/bin/python support/sandpay_target.py --port 8090, then
    .venv/bin/locust -f solutions/locust/lc_flow_console_locustfile.py --headless -u 4 -r 4 -t 10s \\
        --host http://127.0.0.1:8090
"""

import random

from locust import HttpUser, TaskSet, constant, task


class Browse(TaskSet):
    def on_start(self):
        self.client.get("/v1/payments?limit=1", name="GET /v1/payments (open)")

    @task(5)
    def list_payments(self):
        self.client.get("/v1/payments?limit=10", name="GET /v1/payments")

    @task(3)
    def view_payment(self):
        self.client.get(f"/v1/payments/pay_{random.randint(100001, 100250)}", name="GET /v1/payments/{id}")

    @task(2)
    def leave(self):
        self.interrupt()


class MerchantUser(HttpUser):
    wait_time = constant(0.05)
    tasks = {Browse: 3}

    def on_start(self):
        r = self.client.post("/auth/token", json={"client_id": "merchant-1", "client_secret": "secret-1"},
                             name="POST /auth/token")
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    @task(1)
    def run_settlement_report(self):
        self.client.get("/v1/reports/settlement", name="GET /v1/reports/settlement")
