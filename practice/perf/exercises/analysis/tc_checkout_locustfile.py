"""Write the Locust version of the checkout scenario that ``support/tc_checkout.jmx`` runs in JMeter.

The scenario (one virtual merchant):

1. Once, when the user starts: ``POST /auth/token`` with ``{"client_id": "merchant-N", "client_secret": "secret-N"}``
   (N = 1..50, a different merchant for each user: count the users and wrap at 50). Keep the ``access_token``.
2. Then loop, sending ``Authorization: Bearer <token>`` on every request:
   - ``GET /v1/payments?limit=5``
   - ``POST /v1/payments`` with the JSON body ``{"amount_minor": 1250, "currency": "EUR"}`` and a NEW unique
     ``Idempotency-Key`` header each time (a ``uuid4``); keep the ``id`` of the answer
   - ``GET /v1/payments/<that id>``
3. Think for ``TC_WAIT`` seconds (an environment variable, default 0.2) after each iteration.

The four requests are reported under these names, exactly as the JMeter plan names its samplers (pass ``name=``):
``POST /auth/token``, ``GET /v1/payments``, ``POST /v1/payments`` and ``GET /v1/payments/{id}``.
"""

import itertools  # noqa: F401  (you will want it)
import os  # noqa: F401
import uuid  # noqa: F401

from locust import HttpUser, constant, task  # noqa: F401

_merchants = itertools.count(1)


class Merchant(HttpUser):
    # TODO: a constant think time of TC_WAIT seconds (default 0.2)

    def on_start(self):
        raise NotImplementedError("TODO: sign in once and keep the bearer token")

    @task
    def checkout(self):
        raise NotImplementedError("TODO: list, create (unique key), read back")
