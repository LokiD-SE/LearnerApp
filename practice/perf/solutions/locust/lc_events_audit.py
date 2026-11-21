"""A request audit built on Locust's ``request`` event - SOLUTION.

Locust's own statistics keep one row per request name. This audit keeps what a team also asks for after a run:
how many requests were slow, why each failure happened, and which merchant (from the request context) it
happened to. It never imports Locust, so it can be unit-tested; ``install`` receives the ``events`` object.

Run by hand with any locustfile that calls ``install(events, RequestAudit(slow_ms=500), "audit.json")``.
"""

import json
from collections import Counter


class RequestAudit:
    def __init__(self, slow_ms: float = 500.0) -> None:
        self.slow_ms = slow_ms
        self._rows: dict[str, dict] = {}

    def on_request(self, request_type, name, response_time, response_length, exception=None, context=None, **kwargs):
        # **kwargs: Locust adds arguments over time (response, start_time, url ...); never break on a new one.
        row = self._rows.setdefault(f"{request_type} {name}", {
            "requests": 0, "failures": 0, "slow": 0, "reasons": Counter(), "merchants": Counter()})
        row["requests"] += 1
        if response_time > self.slow_ms:
            row["slow"] += 1
        if exception is not None:
            row["failures"] += 1
            row["reasons"][str(exception)] += 1
            merchant = (context or {}).get("merchant")
            if merchant is not None:
                row["merchants"][merchant] += 1

    def summary(self) -> dict:
        return {key: {**row, "reasons": dict(row["reasons"]), "merchants": dict(row["merchants"])}
                for key, row in sorted(self._rows.items())}

    def write(self, path) -> None:
        with open(path, "w") as f:
            json.dump(self.summary(), f, indent=2, sort_keys=True)


def install(events, audit: RequestAudit, path) -> None:
    """Feed every request to ``audit`` and write its summary when the process quits."""
    events.request.add_listener(audit.on_request)
    events.quitting.add_listener(lambda environment, **kwargs: audit.write(path))
