"""Locust user for the metrics lesson: GET /quote, plus a raw per-request log of full-precision response times
(path from $METRICS_RAW_LOG) so a test can recompute Locust's own percentiles."""

import os

from locust import HttpUser, constant, events, task

_raw = open(os.environ["METRICS_RAW_LOG"], "w")  # noqa: SIM115 - closed on quit


@events.request.add_listener
def log_raw(request_type, name, response_time, exception, **kwargs):
    _raw.write(f"{name},{response_time!r}\n")


@events.quitting.add_listener
def close_raw(**kwargs):
    _raw.close()


class QuoteClient(HttpUser):
    wait_time = constant(0)

    @task
    def quote(self):
        self.client.get("/quote", name="GET quote")
