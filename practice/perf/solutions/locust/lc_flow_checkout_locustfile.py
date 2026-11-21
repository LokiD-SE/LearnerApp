"""A checkout as a SequentialTaskSet - reference solution.

Each simulated merchant (merchant-4, merchant-5, ... - no seeded payments, so every payment it reads is one it
created) logs in once in User.on_start. Then the Checkout SequentialTaskSet runs its tasks in the order they are
declared, and repeats:

1. create_payment: POST /v1/payments with a fresh Idempotency-Key; on 201 keep the id in self.payment_id;
2. read_payment:   GET /v1/payments/{id} for that id;
3. replay_payment: POST /v1/payments again with the SAME key and body, expecting Idempotent-Replayed: true.

If a step fails it is marked failed with response.failure(...) and, AFTER the with-block, self.interrupt() hands
control back to the user, which enters a fresh Checkout (new instance, so self.payment_id starts empty). The
interrupt is outside the with-block on purpose: inside it, interrupt() only works safely after failure() or
success() has been called (Locust 2.47 then still reports the request); with no verdict yet, an exception other
than a Locust ResponseError makes the request vanish from the statistics.

Run by hand: .venv/bin/python support/sandpay_target.py --port 8090, then
    .venv/bin/locust -f solutions/locust/lc_flow_checkout_locustfile.py --headless -u 4 -r 4 -t 10s \\
        --host http://127.0.0.1:8090
"""

import itertools
import random
import uuid

from locust import HttpUser, SequentialTaskSet, constant, task

_numbers = itertools.count(4)


class Checkout(SequentialTaskSet):
    def on_start(self):
        self.payment_id = None
        self.key = str(uuid.uuid4())
        self.order = {"amount_minor": random.randint(100, 50000), "currency": "EUR"}

    @task
    def create_payment(self):
        ok = False
        with self.client.post("/v1/payments", json=self.order, headers={"Idempotency-Key": self.key},
                              name="POST /v1/payments", catch_response=True) as r:
            if r.status_code != 201:
                r.failure(f"create: HTTP {r.status_code}")
            else:
                self.payment_id = r.json().get("id")
                ok = self.payment_id is not None
                if not ok:
                    r.failure("create: no id in the response")
        if not ok:
            self.interrupt()

    @task
    def read_payment(self):
        ok = False
        with self.client.get(f"/v1/payments/{self.payment_id}", name="GET /v1/payments/{id}",
                             catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"read back: HTTP {r.status_code}")
            else:
                ok = True
        if not ok:
            self.interrupt()

    @task
    def replay_payment(self):
        with self.client.post("/v1/payments", json=self.order, headers={"Idempotency-Key": self.key},
                              name="POST /v1/payments (replay)", catch_response=True) as r:
            if r.headers.get("Idempotent-Replayed") != "true":
                r.failure(f"replay: not marked as replayed (HTTP {r.status_code})")
            elif r.json().get("id") != self.payment_id:
                r.failure("replay: a different payment id - the retry created a second payment")
        self.interrupt()


class MerchantUser(HttpUser):
    wait_time = constant(0)
    tasks = [Checkout]

    def on_start(self):
        n = next(_numbers)
        r = self.client.post("/auth/token", json={"client_id": f"merchant-{n}", "client_secret": f"secret-{n}"},
                             name="POST /auth/token")
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
