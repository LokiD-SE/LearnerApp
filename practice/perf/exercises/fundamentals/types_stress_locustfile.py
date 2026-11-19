"""A stepped stress test of the SandPay practice API - exercise.

TODO: write StepShape.tick() so the stepped test in tests/fundamentals/test_types_stress.py runs.

Run (from practice/perf, with the target running on port 8090):
    .venv/bin/locust -f exercises/fundamentals/types_stress_locustfile.py --headless \
        --host http://127.0.0.1:8090 --csv results/stress --csv-full-history

The shape reads its staircase from environment variables so tests can make it short:
STEP_START (users in the first step, default 2), STEP_SIZE (users added per step, default 2),
STEP_SECONDS (seconds per step, default 10), STEP_COUNT (number of steps, default 5).

Each user signs in once (on_start; a user whose sign-in was shed signs in again on its next turn) as one of the synthetic merchants, then lists payments with no wait time,
so every user keeps exactly one request in flight - concurrency equals the user count. A 503 (the target
shedding load) or any other non-2xx response counts as a failure, which Locust's HttpUser does by default.
"""

import itertools
import os

from locust import HttpUser, LoadTestShape, constant, task

_merchants = itertools.count(1)


class Merchant(HttpUser):
    wait_time = constant(0)

    def on_start(self):
        self.n = next(_merchants) % 50 + 1
        self.sign_in()

    def sign_in(self):
        # Sign-in can be shed (503) too when the target is saturated. A user without a token signs in again
        # on its next turn instead of sending requests that can only fail with 401.
        r = self.client.post("/auth/token", json={"client_id": f"merchant-{self.n}",
                                                  "client_secret": f"secret-{self.n}"})
        if r.status_code == 200:
            self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    @task
    def list_payments(self):
        if "Authorization" not in self.client.headers:
            self.sign_in()
            return
        self.client.get("/v1/payments?limit=10", name="/v1/payments")


class StepShape(LoadTestShape):
    start = int(os.environ.get("STEP_START", "2"))
    size = int(os.environ.get("STEP_SIZE", "2"))
    seconds = float(os.environ.get("STEP_SECONDS", "10"))
    count = int(os.environ.get("STEP_COUNT", "5"))

    def tick(self):
        """Return (users, spawn_rate) for the current step, or None once STEP_COUNT steps have run.

        Step k (from 0) runs from k * seconds to (k + 1) * seconds with start + size * k users. Spawn the whole
        step within a second (spawn_rate = users). Use self.get_run_time() for the elapsed seconds.
        """
        raise NotImplementedError("TODO: StepShape.tick")
