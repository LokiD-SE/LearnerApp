"""The SandPay merchant console as nested TaskSets - EXERCISE.

Build the locustfile that tests/locust/test_lc_flow_console.py runs with real Locust:

1. One HttpUser class called MerchantUser, wait_time = constant(0.05). In ITS on_start, log in once as merchant-1
   (client_secret "secret-1"): POST /auth/token (name "POST /auth/token"), and keep the access_token on
   self.client.headers as "Authorization: Bearer <token>". A TaskSet's self.client is the same session, so the token
   is sent from inside the TaskSet too.
2. At the top level (the `tasks` attribute, as a dict or with @task), a merchant is in the payments screen 3 times
   as often as they open the slow report:
   - Browse  - a TaskSet, weight 3
   - run_settlement_report - a task, weight 1: GET /v1/reports/settlement (name "GET /v1/reports/settlement")
3. Browse is a TaskSet class. Its on_start sends GET /v1/payments?limit=1 under the name "GET /v1/payments (open)"
   (the user entering the screen). Inside it, three tasks:
   - list_payments, weight 5: GET /v1/payments?limit=10, name "GET /v1/payments"
   - view_payment,  weight 3: GET /v1/payments/pay_<random 100001..100250>, name "GET /v1/payments/{id}"
   - leave,         weight 2: no request - it hands control back to the user. Without that call a simulated user
     would stay in Browse for the whole test.

Try it: .venv/bin/python support/sandpay_target.py --port 8090, then
    .venv/bin/locust -f exercises/locust/lc_flow_console_locustfile.py --headless -u 4 -r 4 -t 10s \\
        --host http://127.0.0.1:8090
and look at the ratios with  --show-task-ratio .
"""

from locust import HttpUser, TaskSet, constant, task  # noqa: F401


class Browse(TaskSet):
    # TODO: on_start, list_payments, view_payment, leave
    pass


class MerchantUser(HttpUser):
    # TODO: wait_time, tasks, on_start (login once), run_settlement_report
    pass
