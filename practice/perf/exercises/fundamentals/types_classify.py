"""Name the performance test type a load profile implements - exercise.

TODO: implement classify() so every test in tests/fundamentals/test_types_classify.py passes.

A profile is a list of stages ``(duration_s, users)``: hold ``users`` virtual users for ``duration_s``
seconds, one stage after another (ramps are left out to keep the rules simple). ``expected_users`` is the
peak load the system is specified for (the "anticipated realistic load" of the ISTQB definition of load
testing).

The rules are applied in this order; the first that matches wins:

1. ``smoke``      - the peak is at most 10% of ``expected_users`` (at least 1 user) and the whole run lasts at
                    most 300 s: a check that the script and the system work at all.
2. ``breakpoint`` - at least 4 stages, users strictly increase from each stage to the next and never go down:
                    load keeps rising until something breaks.
3. ``spike``      - some stage has at least 2x ``expected_users``, lasts at most 10% of the whole run, and is
                    preceded AND followed by a stage at or below ``expected_users``: a sudden burst and a
                    return to normal.
4. ``soak``       - the run lasts at least 4 hours (14,400 s) and the peak is at or below ``expected_users``.
5. ``stress``     - the peak is above ``expected_users``.
6. ``load``       - everything else: up to the expected load, for a moderate time.

``PASS_CRITERIA`` gives, per type, what a run must show to pass - each type answers a different question.
"""

from __future__ import annotations

Stage = tuple[float, int]

TYPES = ("smoke", "load", "stress", "spike", "soak", "breakpoint")

PASS_CRITERIA: dict[str, str] = {
    "smoke": "every request succeeds and the script exercises every step of the flow",
    "load": "response time percentiles and error rate meet the SLO at the expected load",
    "stress": "the system degrades gracefully above the expected load and recovers afterwards",
    "spike": "the burst is absorbed or shed cleanly, and the system returns to its steady state",
    "soak": "response times and resource use (memory, connections, threads) stay flat over hours",
    "breakpoint": "the load at which the SLO is first broken is found, with the limiting resource",
}


def classify(stages: list[Stage], expected_users: int) -> str:
    """Return the test type (one of TYPES) for ``stages``, applying the rules above in order.

    Raise ValueError for an empty profile or a non-positive ``expected_users``.
    """
    raise NotImplementedError("TODO: classify the profile")
