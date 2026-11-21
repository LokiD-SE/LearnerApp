"""The user class for the load shape lesson's demonstrations: a SandPay merchant looking at their payments.

Load shapes decide HOW MANY of these run and WHEN; this file decides what each one does. Pair it with a shape
file on the Locust command line, as the Locust documentation shows for separate user and shape files:

    locust -f support/lc_shape_users.py,support/lc_shape_spike.py --headless --host http://127.0.0.1:8090 --csv run
"""

import itertools

from locust import HttpUser, constant, task

_merchants = itertools.count(1)


class Dashboard(HttpUser):
    host = "http://127.0.0.1:8090"
    wait_time = constant(0.05)

    def on_start(self):
        n = next(_merchants) % 50 + 1  # merchant-1 .. merchant-50
        r = self.client.post("/auth/token", json={"client_id": f"merchant-{n}", "client_secret": f"secret-{n}"})
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    @task
    def list_payments(self):
        self.client.get("/v1/payments?limit=10", name="/v1/payments")
