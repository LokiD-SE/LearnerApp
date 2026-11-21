"""A pass/fail gate for a Locust run - EXERCISE.

By default Locust exits with code 1 when ANY request failed and 0 otherwise, so a pipeline either fails on one
stray error or never looks at response times. Build a gate that decides from the numbers you choose. This module
never imports Locust: ``install`` receives Locust's ``events``; ``violations`` reads a ``RequestStats``-like
object whose ``.total`` has ``num_requests``, ``fail_ratio`` (0-1) and ``get_response_time_percentile(0.95)``
(milliseconds).

``violations(stats, max_fail_ratio, p95_ms)`` returns a list of human-readable reasons, empty when the run passes:
- no requests at all -> ONE reason mentioning "no requests" and nothing else (a run that did nothing must not
  pass, and its ratios are meaningless);
- ``fail_ratio`` above ``max_fail_ratio`` -> a reason that starts with "fail ratio";
- 95th percentile above ``p95_ms`` -> a reason that starts with "p95".
Equal to a limit passes.

``install(events, max_fail_ratio, p95_ms)`` registers a listener on ``events.quitting`` (called with
``environment=...``; accept ``**kwargs``) that sets ``environment.process_exit_code`` to 1 when there are
violations and to 0 when there are none - and logs each reason with ``logging.error``.

Test: .venv/bin/python -m pytest tests/locust/test_lc_events_gate.py
"""

import logging  # noqa: F401


def violations(stats, max_fail_ratio: float, p95_ms: float) -> list[str]:
    raise NotImplementedError


def install(events, max_fail_ratio: float, p95_ms: float) -> None:
    raise NotImplementedError
