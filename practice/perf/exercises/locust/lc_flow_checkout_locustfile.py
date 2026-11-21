"""A checkout as a SequentialTaskSet - EXERCISE.

Complete the locustfile that tests/locust/test_lc_flow_checkout.py runs with real Locust against the practice API.

1. MerchantUser (HttpUser, wait_time = constant(0), tasks = [Checkout]). In its on_start each new user logs in as
   the next merchant number - merchant-4, merchant-5, ... (module-level itertools.count(4); client_secret
   "secret-<n>"; they have no seeded payments, so every payment they read is one they created) - and keeps the
   bearer token on self.client.headers. Name the login "POST /auth/token".
2. Checkout is a SequentialTaskSet: its tasks run in the order they are DECLARED, then repeat. In the TaskSet's
   on_start: self.payment_id = None, a fresh self.key (uuid4) and an order body {"amount_minor", "currency": "EUR"}.
   - create_payment: POST /v1/payments with Idempotency-Key = self.key (name "POST /v1/payments"). Expect 201 and an
     id; keep it in self.payment_id.
   - read_payment:   GET /v1/payments/{self.payment_id} (name "GET /v1/payments/{id}"); expect 200.
   - replay_payment: POST /v1/payments again with the SAME key and body (name "POST /v1/payments (replay)");
     expect the response header Idempotent-Replayed: true and the same id.
   Use catch_response=True on all three. When a step fails call response.failure(reason) and then end the sequence
   with self.interrupt() so the user starts a fresh Checkout - call interrupt() AFTER the with-block (inside it, an exception
   raised before failure() or success() has been called - other than a Locust ResponseError - stops the request
   being recorded). The last step also
   interrupts when it is done, so each cycle gets a new key.

Try it: .venv/bin/python support/sandpay_target.py --port 8090, then
    .venv/bin/locust -f exercises/locust/lc_flow_checkout_locustfile.py --headless -u 4 -r 4 -t 10s \\
        --host http://127.0.0.1:8090
"""

import itertools
import random  # noqa: F401
import uuid  # noqa: F401

from locust import HttpUser, SequentialTaskSet, constant, task  # noqa: F401

_numbers = itertools.count(4)


class Checkout(SequentialTaskSet):
    # TODO: on_start, then create_payment, read_payment, replay_payment IN THAT ORDER
    pass


class MerchantUser(HttpUser):
    # TODO: wait_time, tasks, on_start (login once as the next merchant)
    pass
