"""One Locust user for the bottleneck analysis lesson: a merchant listing payments with no think time, so the
number of users is the number of requests in the system (a closed loop, as in the lesson's own probe)."""

from locust import HttpUser, constant, task


class Merchant(HttpUser):
    wait_time = constant(0)

    def on_start(self):
        r = self.client.post("/auth/token", json={"client_id": "merchant-1", "client_secret": "secret-1"},
                             name="/auth/token")
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    @task
    def list_payments(self):
        self.client.get("/v1/payments?limit=1", name="/v1/payments")
