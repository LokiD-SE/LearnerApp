"""Authentication and correlation in Locust - EXERCISE.

Against the shared practice API (support/sandpay_target.py). Each simulated merchant must:

1. on_start: get a bearer token for its own merchant (merchant-4, merchant-5, ... - merchants without seeded
   payments, so every payment it can read is one it created) and put it in self.client.headers, so every
   later request carries it;
2. per iteration, run one payment flow with three correlated steps:
   - "POST /v1/payments": create with a fresh Idempotency-Key; expect 201 and keep the returned id;
   - "GET /v1/payments/{id}": read that id back; expect 200, the same id and this user's merchant;
   - "POST /v1/payments (replay)": resend the SAME key and body; expect the Idempotent-Replayed: true header
     and the same id (a retry must not create a second payment).
   If a step fails, mark it failed and stop the flow: never send the next step with an id you don't have.

The four request names above plus "POST /auth/token" are checked exactly.

Test: .venv/bin/python -m pytest tests/locust/test_lc_valid_flow.py
Run by hand: .venv/bin/python support/sandpay_target.py --port 8090, then
    .venv/bin/locust -f exercises/locust/lc_valid_flow_locustfile.py --headless -u 4 -r 4 -t 10s \\
        --host http://127.0.0.1:8090
"""

import itertools
import random  # noqa: F401
import uuid  # noqa: F401

from locust import HttpUser, constant, task

_numbers = itertools.count(4)


class PaymentFlowUser(HttpUser):
    wait_time = constant(0)

    def on_start(self):
        n = next(_numbers)
        self.merchant = f"merchant-{n}"
        # TODO: POST /auth/token {"client_id": ..., "client_secret": f"secret-{n}"} named "POST /auth/token",
        #       then set self.client.headers["Authorization"] = "Bearer <access_token>".
        raise NotImplementedError

    @task
    def payment_flow(self):
        # TODO: create -> read back -> replay, each with catch_response=True and the names in the docstring.
        raise NotImplementedError
