"""A paced Locust user (reference solution).

Goal: 5 users together send 20 payment-list requests per second to the SandPay practice API - each user
runs its task 4 times per second, whatever the response time, as long as the server keeps up.

Each user gets a token once (on_start), then every task sends one GET /v1/payments?limit=1. Run it:
    .venv/bin/locust -f solutions/fundamentals/little_paced_locustfile.py --headless -u 5 -r 50 -t 10s \
        --host http://127.0.0.1:8090
"""

from locust import HttpUser, constant_throughput, task

TARGET_RPS = 20
USERS = 5


class PacedMerchant(HttpUser):
    # 20 requests/s over 5 users = 4 task runs per second per user (one request per task). constant_throughput
    # waits "an adaptive time that ensures the task runs (at most) X times per second" (Locust docs).
    wait_time = constant_throughput(TARGET_RPS / USERS)

    def on_start(self):
        r = self.client.post("/auth/token", json={"client_id": "merchant-1", "client_secret": "secret-1"},
                             name="POST /auth/token")
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    @task
    def list_payments(self):
        self.client.get("/v1/payments?limit=1", name="GET /v1/payments")
