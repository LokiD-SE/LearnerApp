"""Exercise pcap_locustfile: the settlement-day workload for the SandPay API as a Locust script.

One virtual merchant (user) must:

1. sign in ONCE (``on_start``), as ``merchant-N`` / ``secret-N`` with N cycling through 1, 2, 3 (the practice API
   only seeds payments for those three merchants), and send ``Authorization: Bearer <token>`` afterwards;
2. read its first page of payments ONCE (``limit=50``) and keep the payment ids - the "setup" step;
3. then repeat ONE transaction at a time, picked by weight, waiting ``THINK`` seconds between them:

       POST /v1/payments              weight 8   (40 %)  fresh Idempotency-Key header every time
       GET  /v1/payments              weight 6   (30 %)  ?limit=10
       GET  /v1/payments/{id}         weight 5   (25 %)  an id from the setup page
       GET  /v1/reports/settlement    weight 1   ( 5 %)

Request names matter - the report groups, judges and compares by them. Use EXACTLY these ``name=`` values:
``POST /auth/token``, ``setup: GET /v1/payments``, ``POST /v1/payments``, ``GET /v1/payments``,
``GET /v1/payments/{id}`` (one name for every id), ``GET /v1/reports/settlement``.

``THINK`` comes from the environment variable ``PCAP_THINK`` (seconds, default 0.3).
"""

import itertools
import os
import random
import uuid

from locust import HttpUser, constant, task

THINK = float(os.environ.get("PCAP_THINK", "0.3"))
_merchants = itertools.count(0)


class Merchant(HttpUser):
    wait_time = constant(THINK)

    def on_start(self):
        # TODO: sign in once, set the Authorization header, read the setup page and keep the payment ids.
        raise NotImplementedError("sign in and read the setup page")

    # TODO: four @task methods with the weights and request names in the module docstring.
