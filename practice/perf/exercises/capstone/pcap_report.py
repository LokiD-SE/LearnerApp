"""Exercise pcap_report: from two tools' results to one honest report.

Reuse the earlier lessons through ``pcap_fixture.ref`` (their reference code): ``ref.Verdict`` is the result type and
``ref.evaluate`` judges JMeter samples with the SLO lesson's rules. You write the rest.

``steady_samples(samples, warmup_s)``
    JMeter ``ref.Sample`` objects that started at least ``warmup_s`` seconds after the EARLIEST sample (so both epoch
    and rebased timestamps work); empty in, empty out.

``locust_percentile(response_times, pct)``
    nearest-rank percentile of Locust's histogram ``{"53": 12, "240": 3}`` (rounded milliseconds -> count); an empty
    histogram or a ``pct`` outside (0, 100] raises ``ValueError``.

``locust_verdicts(entries, requirements, min_samples=100)``
    one ``ref.Verdict(transaction, kind, target, observed, status, samples, note)`` per requirement, with the SAME rules
    as ``ref.evaluate`` but from Locust ``--json-file`` entries (``name``, ``num_requests``, ``num_failures``,
    ``response_times``, ``start_time``, ``last_request_timestamp``):

    - ``inconclusive`` (observed None, note ``"only N samples (need M)"``) with fewer than ``min_samples`` requests,
      or no entry at all;
    - ``inconclusive`` (note mentions "users") when the load is stated in users - Locust's totals cannot show it;
    - rate = requests / (last_request_timestamp - start_time); below 90 % of a ``req/s`` load the status is
      ``inconclusive`` with a note starting ``"load not reached"`` (observed is still filled in);
    - latency observed = ``locust_percentile`` at the requirement's percentile, pass when <= the threshold;
    - errors observed = ``num_failures / num_requests`` in percent rounded to 2 decimals, pass when <= the maximum;
    - otherwise ``pass`` or ``fail`` with note ``"achieved X.X req/s"``.

``compare_tools(a, b, tolerance=0.30, slack_ms=10.0)``
    ``{(transaction, kind): "agree" | "differ" | "not-comparable"}`` over the requirements in either list.
    ``not-comparable``: missing from one list, or either ``observed`` is None. ``agree``: equal status AND the observed
    values differ by at most ``max(slack_ms, tolerance * the smaller)`` (Locust rounds to two significant digits).

``final_call(by_tool, agreement=None)``
    ``"fail"`` if any verdict fails; ``"pass"`` only if every tool has verdicts, all pass and no comparison says
    ``differ``; otherwise ``"inconclusive"``. No tools: ``ValueError``.

``render_report(title, plan, by_tool, agreement, caveats)``
    Markdown: ``# title``, then ``## Verdict``, ``## Plan``, ``## Evidence``, ``## Tool agreement``, ``## Caveats``.
    The verdict line is ``**PASS**``, ``**FAIL**`` or ``**INCONCLUSIVE**`` followed by `` - `` and the reason (the failing
    transactions with their tool, or what blocks a verdict). The evidence is a table with one row per tool and
    requirement. No caveats: ``ValueError`` - a report without them is not finished.
"""

import math  # noqa: F401

from pcap_fixture import NOT_USER_TRAFFIC, ref  # noqa: F401

LOAD_TOLERANCE = 0.9


def steady_samples(samples, warmup_s):
    raise NotImplementedError("drop the warm-up")


def locust_percentile(response_times, pct):
    raise NotImplementedError("nearest rank over the histogram")


def locust_verdicts(entries, requirements, min_samples=100):
    raise NotImplementedError("judge Locust totals with the SLO rules")


def compare_tools(a, b, tolerance=0.30, slack_ms=10.0):
    raise NotImplementedError("agree, differ or not-comparable")


def final_call(by_tool, agreement=None):
    raise NotImplementedError("one overall call")


def render_report(title, plan, by_tool, agreement, caveats):
    raise NotImplementedError("the Markdown report")
