"""Authentication and correlation in Locust - reference solution.

Against the shared practice API (support/sandpay_target.py). Each simulated merchant:

1. on_start: gets a bearer token for its own merchant (merchant-4, merchant-5, ... - merchants without seeded
   payments, so every payment it can read is one it created) and puts it in self.client.headers, so every
   later request carries it;
2. per iteration, one payment flow with three correlated steps:
   - "POST /v1/payments": create with a fresh Idempotency-Key; expect 201 and keep the returned id;
   - "GET /v1/payments/{id}": read that id back; expect 200, the same id and this user's merchant;
   - "POST /v1/payments (replay)": resend the SAME key and body; expect the Idempotent-Replayed: true header
     and the same id (a retry must not create a second payment).
   If a step fails, mark it failed and stop the flow: never send the next step with an id you don't have.

Run by hand: .venv/bin/python support/sandpay_target.py --port 8090, then
    .venv/bin/locust -f solutions/locust/lc_valid_flow_locustfile.py --headless -u 4 -r 4 -t 10s \\
        --host http://127.0.0.1:8090
"""

import itertools
import random
import uuid

from locust import HttpUser, constant, task

_numbers = itertools.count(4)


class PaymentFlowUser(HttpUser):
    wait_time = constant(0)

    def on_start(self):
        n = next(_numbers)
        self.merchant = f"merchant-{n}"
        r = self.client.post("/auth/token", json={"client_id": self.merchant, "client_secret": f"secret-{n}"},
                             name="POST /auth/token")
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    @task
    def payment_flow(self):
        key = str(uuid.uuid4())
        order = {"amount_minor": random.randint(100, 50000), "currency": "EUR"}

        with self.client.post("/v1/payments", json=order, headers={"Idempotency-Key": key},
                              name="POST /v1/payments", catch_response=True) as r:
            if r.status_code != 201:
                r.failure(f"create: HTTP {r.status_code}")
                return
            payment_id = r.json().get("id")
            if not payment_id:
                r.failure("create: no id in the response")
                return

        with self.client.get(f"/v1/payments/{payment_id}", name="GET /v1/payments/{id}", catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"read back: HTTP {r.status_code}")
                return
            body = r.json()
            if body.get("id") != payment_id or body.get("merchant") != self.merchant:
                r.failure(f"read back: got {body.get('id')} for {body.get('merchant')}")
                return

        with self.client.post("/v1/payments", json=order, headers={"Idempotency-Key": key},
                              name="POST /v1/payments (replay)", catch_response=True) as r:
            if r.headers.get("Idempotent-Replayed") != "true":
                r.failure(f"replay: not marked as replayed (HTTP {r.status_code})")
            elif r.json().get("id") != payment_id:
                r.failure("replay: a different payment id - the retry created a second payment")
