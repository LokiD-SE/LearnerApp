"""Validating a gateway that always answers 200 - EXERCISE.

The SandPay legacy gateway (support/lc_valid_fixture.py) puts the real outcome of a charge in the body, so a
status-code check alone sees 0% errors. Each simulated merchant must:

1. log in once (on_start) - the session cookie it gets back is kept by the HttpSession (a requests.Session);
2. per iteration, charge a card with catch_response=True and mark the request
   - failed "not JSON: ..." when the body is not JSON (the gateway's HTML error page),
   - failed "declined: <decline_code>" when status is "declined",
   - successful when status is "approved";
3. only after an approved charge: void it, then look it up again and expect 404 - for that lookup a 404 is
   the CORRECT answer (mark it a success) and a 200 is the failure ("voided charge still visible").

Request names (the test checks them exactly):
    POST /gateway/login
    POST /gateway/charges
    POST /gateway/charges/{id}/void
    GET /gateway/charges/{id} (voided)

Test: .venv/bin/python -m pytest tests/locust/test_lc_valid_gateway.py
Run by hand: .venv/bin/python support/lc_valid_fixture.py --port 8091, then
    .venv/bin/locust -f exercises/locust/lc_valid_gateway_locustfile.py --headless -u 4 -r 4 -t 10s \\
        --host http://127.0.0.1:8091
"""

import itertools
from json import JSONDecodeError  # noqa: F401 - you will need it

from locust import HttpUser, constant, task

_numbers = itertools.count(1)


class GatewayMerchant(HttpUser):
    wait_time = constant(0)  # the exercise counts outcomes; a real test paces users (see locust-fundamentals)

    def on_start(self):
        n = next(_numbers)
        # TODO: POST /gateway/login with {"username": f"merchant-{n}", "password": f"secret-{n}"},
        #       named "POST /gateway/login"; mark it failed unless it is 200 and set the gw_session cookie.
        raise NotImplementedError

    @task
    def charge_and_void(self):
        # TODO: POST /gateway/charges {"amount_minor": 1250, "currency": "EUR"} with catch_response=True and the
        #       rules in the docstring; then, for approved charges only, void and look up (expect 404).
        raise NotImplementedError
