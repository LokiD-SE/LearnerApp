"""A paced Locust user.

Goal: 5 users together send 20 payment-list requests per second to the SandPay practice API - each user
runs its task the same number of times per second, whatever the response time, as long as the server keeps up.

TODO:
1. Set wait_time so each of the 5 users runs its task TARGET_RPS / USERS times per second (see Locust's
   constant_throughput). constant(0) - the placeholder - makes a closed loop with no waiting at all.
2. on_start: POST /auth/token with {"client_id": "merchant-1", "client_secret": "secret-1"} (name it
   "POST /auth/token") and send the returned access_token as "Authorization: Bearer <token>" on every request.
3. The task: GET /v1/payments?limit=1, named "GET /v1/payments".

Run: .venv/bin/python -m pytest tests/fundamentals/test_little_paced_locustfile.py
"""

from locust import HttpUser, constant, task

TARGET_RPS = 20
USERS = 5


class PacedMerchant(HttpUser):
    wait_time = constant(0)  # TODO: pace it

    def on_start(self):
        pass  # TODO: get a token and keep it on self.client.headers

    @task
    def list_payments(self):
        raise NotImplementedError("send GET /v1/payments?limit=1")
