"""Exercise: a pre-run checklist for a load test (lesson "Test environments and test data").

``check_run_plan(plan)`` reads a run plan (a dict, as a team might keep in YAML next to the test) and returns
the problem codes that should stop the run, in the order of ``CHECKS``. An empty list means "go".

Plan fields (all required):

- ``tool``: ``"jmeter"`` or ``"locust"``
- ``gui``: True if the run would use the JMeter GUI or the Locust web UI to drive the test
- ``listeners``: names of JMeter listeners enabled in the plan (``[]`` for Locust)
- ``target_host``: the host the load goes to
- ``approved_hosts``: hosts the written test approval covers
- ``generator_cores``: CPU cores on the load generator machine
- ``processes``: load generator processes (Locust workers; 1 for a single JMeter instance)
- ``expected_rps``: the request rate the test must produce
- ``rps_per_process``: what one generator process sustained in a calibration run on this machine
- ``virtual_users``: concurrent virtual users
- ``unique_data_rows``: rows of unique test data (accounts, cards, keys) available to the run
- ``warmup_s``: seconds of warm-up excluded from the results
- ``duration_s``: total run length in seconds, warm-up included
- ``min_steady_s``: the steady-state length the requirement asks for
- ``state_reset``: True if the environment's data is reset (or the run uses fresh data) before the run
- ``generator_monitored``: True if CPU, memory and network of the generator are recorded during the run
"""

from __future__ import annotations

# The order the problems are reported in.
CHECKS = (
    "scope",                # target_host not in approved_hosts
    "cli-mode",             # gui is True (JMeter: "Don't run load test using GUI mode!")
    "heavy-listeners",      # JMeter "View Results Tree" or "View Results in Table" enabled
    "too-many-processes",   # processes > generator_cores (Locust: one worker per core)
    "generator-capacity",   # expected_rps > rps_per_process * processes * 0.8 (keep 20 % headroom)
    "data-volume",          # unique_data_rows < virtual_users
    "no-warm-up",           # warmup_s <= 0
    "steady-state-too-short",  # duration_s - warmup_s < min_steady_s
    "state-not-reset",      # state_reset is False
    "generator-not-monitored",  # generator_monitored is False
)

HEAVY_LISTENERS = ("View Results Tree", "View Results in Table")
HEADROOM = 0.8


def check_run_plan(plan: dict) -> list[str]:
    """Return the codes of CHECKS that fail for ``plan``, in the order of CHECKS. [] means "go".

    TODO: one ``if`` per check - the comment next to each code in CHECKS is its rule. Use HEAVY_LISTENERS
    and HEADROOM. Heavy listeners only matter when ``tool`` is ``"jmeter"``.
    """
    raise NotImplementedError("check_run_plan")
