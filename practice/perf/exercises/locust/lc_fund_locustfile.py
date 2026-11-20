"""Your first SandPay locustfile.

Build a merchant dashboard user that tests/locust/test_lc_fund_locustfile.py runs with real Locust:

1. One HttpUser class called MerchantUser, with host = "http://127.0.0.1:8090" as its default (the tests pass
   --host, which overrides it).
2. Each user logs in ONCE, before its first task: POST /auth/token with
   {"client_id": "merchant-1", "client_secret": "secret-1"}, then sends the returned access_token as
   "Authorization: Bearer <token>" on every later request (self.client.headers).
3. Two tasks, picked 3 : 1 -
   - list_payments: GET /v1/payments?limit=10, reported under the name "/v1/payments"
   - view_payment:  GET /v1/payments/<id> for a random id from pay_100001 .. pay_100250 (merchant-1's payments),
     all reported under ONE name, "/v1/payments/[id]"
4. Each user runs at most 2 tasks per second, whatever the response time (pick the right wait_time function).

Try it by hand: .venv/bin/python support/sandpay_target.py --port 8090, then in another terminal
    .venv/bin/locust -f exercises/locust/lc_fund_locustfile.py --headless -u 4 -r 4 -t 10s
"""

from locust import HttpUser, task  # TODO: import the wait_time function you need


class MerchantUser(HttpUser):
    # TODO: host and wait_time

    # TODO: on_start - log in once and keep the token on self.client.headers

    @task
    def list_payments(self):
        # TODO: weight 3, the right URL and name=
        self.client.get("/v1/payments")

    # TODO: view_payment, weight 1
