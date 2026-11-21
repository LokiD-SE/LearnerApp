"""A step-load shape for the SandPay merchant dashboard.

The test must go through three steps by itself, with no -u, -r or -t on the command line:

- seconds 0-3: 1 user, seconds 3-6: 3 users, seconds 6-9: 5 users, all started at 10 users per second;
- after second 9 the test stops on its own.

Complete ``StepShape.tick`` (``Dashboard`` is finished). Try it by hand:

    .venv/bin/python support/sandpay_target.py --port 8090
    .venv/bin/locust -f exercises/locust/lc_shape_locustfile.py --headless --host http://127.0.0.1:8090 --csv run

then read run_stats_history.csv: the "User Count" column should climb 1, 3, 5.
"""

import itertools

from locust import HttpUser, LoadTestShape, constant, task

_merchants = itertools.count(1)


class Dashboard(HttpUser):
    host = "http://127.0.0.1:8090"
    wait_time = constant(0.1)

    def on_start(self):
        n = next(_merchants) % 50 + 1  # merchant-1 .. merchant-50
        r = self.client.post("/auth/token", json={"client_id": f"merchant-{n}", "client_secret": f"secret-{n}"})
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    @task
    def list_payments(self):
        self.client.get("/v1/payments?limit=10", name="/v1/payments")


class StepShape(LoadTestShape):
    # "duration" is the END of the stage, in seconds since the start of the test
    stages = [
        {"duration": 3, "users": 1, "spawn_rate": 10},
        {"duration": 6, "users": 3, "spawn_rate": 10},
        {"duration": 9, "users": 5, "spawn_rate": 10},
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None  # no stage left: Locust stops the test
