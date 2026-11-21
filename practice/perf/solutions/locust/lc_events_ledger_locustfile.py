"""A Locust user for the SandPay ledger - SOLUTION. Run by hand:

    .venv/bin/python -c "import sys; sys.path.insert(0, 'support'); import lc_events_fixture as f, time; \
        l = f.serve().__enter__(); print(l.host); time.sleep(3600)"
    .venv/bin/locust -f solutions/locust/lc_events_ledger_locustfile.py --headless -u 4 -r 4 -t 10s --host <host>
"""

import os
import sys

from locust import User, constant, task

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lc_events_client import LedgerClient  # noqa: E402


class LedgerUser(User):
    wait_time = constant(0)

    def on_start(self):
        self.client = LedgerClient(self.host, self.environment.events.request)

    def on_stop(self):
        self.client.close()

    @task(3)
    def balance(self):
        self.client.balance("merchant-1")

    @task(1)
    def transfer(self):
        self.client.transfer("merchant-1", "merchant-2", 1250)
