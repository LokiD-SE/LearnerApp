"""The Locust user the payment-systems lesson drives with the retry rules from ``analysis/ppay_retry.py``.

It imports ``ppay_retry`` from the folder named by the ``PPAY_DIR`` environment variable (``ppay_fixture.run_pay_locust``
sets it to ``exercises/analysis`` or, with ``PERF_TARGET=solutions``, ``solutions/analysis``), makes every payment through
``submit_payment`` and appends one ledger record per LOGICAL payment to the JSON-lines file named by ``PPAY_LEDGER``.
Locust itself records every attempt: a 503, a 500 or a timeout is a failure row, a retry that works is a success row.
"""

import itertools
import json
import os
import sys
import time

sys.path.insert(0, os.environ["PPAY_DIR"])

import ppay_retry  # noqa: E402
from locust import HttpUser, constant, task  # noqa: E402

_merchants = itertools.count(1)
_logical = itertools.count(1)


class Merchant(HttpUser):
    wait_time = constant(0.01)

    def on_start(self):
        n = next(_merchants) % 50 + 1
        for _ in range(40):  # a burst of logins can meet a busy API; the user waits and asks again
            r = self.client.post("/auth/token", json={"client_id": f"merchant-{n}", "client_secret": f"secret-{n}"},
                                 name="/auth/token")
            if r.status_code == 200:
                self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
                return
            time.sleep(0.05)
        raise RuntimeError("could not log in")

    def _send(self, key):
        with self.client.post("/v1/payments", json={"amount_minor": 1250, "currency": "EUR"},
                              headers={"Idempotency-Key": key}, name="POST /v1/payments", timeout=3,
                              catch_response=True) as r:
            if r.status_code == 0:
                r.failure("no response")
                return None, {}
            if not 200 <= r.status_code < 300:
                r.failure(f"HTTP {r.status_code}")
            return r.status_code, dict(r.headers)

    @task
    def pay(self):
        record = ppay_retry.submit_payment(self._send, f"pay-{next(_logical)}")
        with open(os.environ["PPAY_LEDGER"], "a") as f:
            f.write(json.dumps(record) + "\n")
