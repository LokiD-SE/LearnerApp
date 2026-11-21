"""A Locust user for the SandPay ledger - EXERCISE (uses your LedgerClient from lc_events_client.py).

``LedgerUser`` is a plain Locust ``User`` (there is no HTTP client to inherit):
1. each simulated user gets its own LedgerClient in on_start - ``self.host`` is the ``--host`` value - built with
   ``self.environment.events.request`` so its calls land in Locust's statistics - and closes it in on_stop;
2. two tasks, weight 3 : 1 - ``balance`` (BALANCE merchant-1) and ``transfer`` (TRANSFER merchant-1 merchant-2
   1250);
3. no waiting between tasks (``constant(0)``): the exercise counts outcomes.

Test: .venv/bin/python -m pytest tests/locust/test_lc_events_client.py
"""

import os
import sys

from locust import User, constant, task  # noqa: F401

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lc_events_client import LedgerClient  # noqa: E402,F401


class LedgerUser(User):
    # TODO: wait_time, on_start, on_stop and the two tasks
    pass
