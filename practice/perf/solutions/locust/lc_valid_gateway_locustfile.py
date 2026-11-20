"""Validating a gateway that always answers 200 - reference solution.

The SandPay legacy gateway (support/lc_valid_fixture.py) puts the real outcome of a charge in the body, so a
status-code check alone sees 0% errors. Each simulated merchant:

1. logs in once (on_start); the session cookie it gets back is kept by the HttpSession (a requests.Session);
2. per iteration, charges a card with catch_response=True and marks the request
   - failed "not JSON: ..." when the body is not JSON (the gateway's HTML error page),
   - failed "declined: <decline_code>" when status is "declined",
   - successful when status is "approved";
3. only after an approved charge: voids it, then looks it up again and expects 404 - for that lookup a 404 is
   the CORRECT answer (mark it a success) and a 200 is the failure ("voided charge still visible").

Request names (the test checks them exactly):
    POST /gateway/login
    POST /gateway/charges
    POST /gateway/charges/{id}/void
    GET /gateway/charges/{id} (voided)

Run by hand: .venv/bin/python support/lc_valid_fixture.py --port 8091, then
    .venv/bin/locust -f solutions/locust/lc_valid_gateway_locustfile.py --headless -u 4 -r 4 -t 10s \\
        --host http://127.0.0.1:8091
"""

import itertools
from json import JSONDecodeError

from locust import HttpUser, constant, task

_numbers = itertools.count(1)


class GatewayMerchant(HttpUser):
    wait_time = constant(0)  # the exercise counts outcomes; a real test paces users (see locust-fundamentals)

    def on_start(self):
        n = next(_numbers)
        with self.client.post("/gateway/login", json={"username": f"merchant-{n}", "password": f"secret-{n}"},
                              name="POST /gateway/login", catch_response=True) as r:
            if r.status_code != 200 or "gw_session" not in self.client.cookies:
                r.failure(f"login failed: HTTP {r.status_code}")

    @task
    def charge_and_void(self):
        charge_id = None
        with self.client.post("/gateway/charges", json={"amount_minor": 1250, "currency": "EUR"},
                              name="POST /gateway/charges", catch_response=True) as r:
            try:
                body = r.json()
            except JSONDecodeError:
                r.failure(f"not JSON: HTTP {r.status_code} {r.headers.get('Content-Type')}")
                return
            if body.get("status") == "declined":
                r.failure(f"declined: {body.get('decline_code')}")
                return
            if body.get("status") != "approved" or "id" not in body:
                r.failure(f"unexpected charge body: {body}")
                return
            charge_id = body["id"]
            r.success()

        self.client.post(f"/gateway/charges/{charge_id}/void", name="POST /gateway/charges/{id}/void")
        with self.client.get(f"/gateway/charges/{charge_id}", name="GET /gateway/charges/{id} (voided)",
                             catch_response=True) as r:
            if r.status_code == 404:
                r.success()
            else:
                r.failure(f"voided charge still visible: HTTP {r.status_code}")
