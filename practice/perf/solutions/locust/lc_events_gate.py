"""A pass/fail gate for a Locust run - SOLUTION.

By default Locust exits with code 1 when ANY request failed and 0 otherwise, so a pipeline either fails on one
stray error or never looks at response times. A gate sets the exit code from the numbers you chose. It never
imports Locust: ``install`` receives the ``events`` object, and ``violations`` reads a ``RequestStats``-like
object (``stats.total``).
"""

import logging


def violations(stats, max_fail_ratio: float, p95_ms: float) -> list[str]:
    total = stats.total
    if total.num_requests == 0:
        return ["no requests were made - the run proves nothing"]
    found = []
    if total.fail_ratio > max_fail_ratio:
        found.append(f"fail ratio {total.fail_ratio:.1%} is above the limit of {max_fail_ratio:.1%}")
    p95 = total.get_response_time_percentile(0.95)
    if p95 > p95_ms:
        found.append(f"p95 {p95:.0f} ms is above the limit of {p95_ms:.0f} ms")
    return found


def install(events, max_fail_ratio: float, p95_ms: float) -> None:
    """On ``events.quitting`` set ``environment.process_exit_code`` to 1 if there are violations, else 0."""

    def gate(environment, **kwargs):
        found = violations(environment.stats, max_fail_ratio, p95_ms)
        for reason in found:
            logging.error("GATE FAILED: %s", reason)
        environment.process_exit_code = 1 if found else 0

    events.quitting.add_listener(gate)
