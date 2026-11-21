"""From two tools' results to one honest report (reference solution).

Reuses, through ``pcap_fixture.ref``, the reference code of earlier lessons: ``ref.Verdict`` and the verdict rules of
the SLO lesson (``ref.evaluate`` judges JMeter samples). This module adds what the capstone needs on top:

- ``steady_samples``  drop the warm-up from JMeter samples;
- ``locust_percentile`` and ``locust_verdicts``  judge Locust's ``--json-file`` totals with the SAME rules;
- ``compare_tools``   do the two tools tell the same story?
- ``final_call``      one overall call (pass only when nothing is failing, missing or contradicted);
- ``render_report``   the Markdown report, with the evidence and the caveats next to the verdict.
"""

import math

from pcap_fixture import NOT_USER_TRAFFIC, ref

LOAD_TOLERANCE = 0.9


def steady_samples(samples, warmup_s):
    """Samples that started at least ``warmup_s`` seconds after the earliest sample (so epoch or rebased times work)."""
    if not samples:
        return []
    first = min(s.timestamp_ms for s in samples)
    return [s for s in samples if s.timestamp_ms - first >= warmup_s * 1000]


def locust_percentile(response_times, pct):
    """Nearest-rank percentile of Locust's histogram ``{"53": 12, "240": 3, ...}`` (rounded ms -> count)."""
    if not response_times:
        raise ValueError("empty histogram")
    if not 0 < pct <= 100:
        raise ValueError("pct must be in (0, 100]")
    buckets = sorted((int(ms), n) for ms, n in response_times.items())
    total = sum(n for _, n in buckets)
    rank = math.ceil(pct / 100 * total)
    seen = 0
    for ms, n in buckets:
        seen += n
        if seen >= rank:
            return ms
    raise AssertionError("unreachable")


def locust_verdicts(entries, requirements, min_samples=100):
    """One ``ref.Verdict`` per requirement from Locust ``--json-file`` entries (the same rules as ``ref.evaluate``).

    ``inconclusive`` when the transaction has fewer than ``min_samples`` requests, when its rate (requests divided by
    ``last_request_timestamp - start_time``) is below 90 % of a ``req/s`` load, or when the load is stated in users
    (Locust's totals do not say how many users were active at a moment). Otherwise latency is the nearest-rank
    percentile of the histogram and an error requirement compares failures / requests, in percent, rounded to 2
    decimals. Note the histogram holds failed requests too, unlike the JMeter rule.
    """
    by_name = {e["name"]: e for e in entries}
    verdicts = []
    for req in requirements:
        target = req.threshold_ms if req.kind == "latency" else req.max_error_percent
        entry = by_name.get(req.transaction)
        n = entry["num_requests"] if entry else 0
        if n < min_samples:
            verdicts.append(ref.Verdict(req.transaction, req.kind, target, None, "inconclusive", n,
                                        f"only {n} samples (need {min_samples})"))
            continue
        if req.load_unit != "req/s":
            verdicts.append(ref.Verdict(req.transaction, req.kind, target, None, "inconclusive", n,
                                        "load stated in users cannot be checked from Locust totals"))
            continue
        span = max(entry["last_request_timestamp"] - entry["start_time"], 0.001)
        rate = n / span
        if req.kind == "latency":
            observed = locust_percentile(entry["response_times"], req.percentile)
            passed = observed <= req.threshold_ms
        else:
            observed = round(100 * entry["num_failures"] / n, 2)
            passed = observed <= req.max_error_percent
        if rate < LOAD_TOLERANCE * req.load:
            verdicts.append(ref.Verdict(req.transaction, req.kind, target, observed, "inconclusive", n,
                                        f"load not reached: achieved {rate:.1f} req/s, required {req.load:g} req/s"))
        else:
            verdicts.append(ref.Verdict(req.transaction, req.kind, target, observed,
                                        "pass" if passed else "fail", n, f"achieved {rate:.1f} req/s"))
    return verdicts


def compare_tools(a, b, tolerance=0.30, slack_ms=10.0):
    """Do two tools agree, requirement by requirement?  Returns ``{(transaction, kind): "agree" | "differ" |
    "not-comparable"}``.

    ``not-comparable``: the requirement is missing from one tool, or either tool has no observed value.
    ``agree``: same status, and the observed values differ by at most ``max(slack_ms, tolerance * the smaller)``
    (the slack covers Locust's rounding of response times to two significant digits). Otherwise ``differ``.
    """
    left = {(v.transaction, v.kind): v for v in a}
    right = {(v.transaction, v.kind): v for v in b}
    out = {}
    for key in sorted(set(left) | set(right)):
        x, y = left.get(key), right.get(key)
        if x is None or y is None or x.observed is None or y.observed is None:
            out[key] = "not-comparable"
            continue
        gap = abs(x.observed - y.observed)
        limit = max(slack_ms, tolerance * min(x.observed, y.observed))
        out[key] = "agree" if x.status == y.status and gap <= limit else "differ"
    return out


def final_call(by_tool, agreement=None):
    """``"pass"``, ``"fail"`` or ``"inconclusive"`` for the whole engagement.

    ``fail`` if any verdict in any tool fails. ``pass`` only if every tool has verdicts, all of them pass, and no
    comparison says ``differ``. Everything else is ``inconclusive``. No tools at all raises ``ValueError``.
    """
    if not by_tool:
        raise ValueError("no tool results")
    verdicts = [v for vs in by_tool.values() for v in vs]
    if any(v.status == "fail" for v in verdicts):
        return "fail"
    empty = any(not vs for vs in by_tool.values())
    differ = agreement is not None and "differ" in agreement.values()
    if empty or differ or any(v.status != "pass" for v in verdicts):
        return "inconclusive"
    return "pass"


def render_report(title, plan, by_tool, agreement, caveats):
    """The Markdown report: ``# title`` then ``## Verdict``, ``## Plan``, ``## Evidence``, ``## Tool agreement`` and
    ``## Caveats`` in that order.

    The verdict line is ``**PASS**``, ``**FAIL**`` or ``**INCONCLUSIVE**`` (from ``final_call``) plus the reason:
    which requirements failed, or what stops a verdict. The evidence is a table with one row per tool and
    requirement. A report with no caveats is not finished: ``ValueError``.
    """
    if not caveats:
        raise ValueError("a report needs its caveats")
    call = final_call(by_tool, agreement)
    rows = [(tool, v) for tool, vs in by_tool.items() for v in vs]
    if call == "pass":
        reason = "every requirement met in every tool at the stated load"
    elif call == "fail":
        reason = "failed: " + ", ".join(f"{v.transaction} ({tool})" for tool, v in rows if v.status == "fail")
    else:
        causes = [f"{v.transaction} ({tool}): {v.note}" for tool, v in rows if v.status == "inconclusive"]
        causes += [f"{tx} [{kind}]: the tools differ" for (tx, kind), s in (agreement or {}).items() if s == "differ"]
        causes += [f"{tool}: no verdicts" for tool, vs in by_tool.items() if not vs]
        reason = "cannot support a verdict: " + "; ".join(causes)
    lines = [f"# {title}", "", "## Verdict", "", f"**{call.upper()}** - {reason}", "", "## Plan", "",
             f"- Target: {sum(plan['rates'].values()):g} req/s with {plan['users']} users",
             f"- API ceiling: {plan['ceiling_rps']:.0f} req/s (utilisation {plan['utilisation']:.0%})",
             f"- Run length: at least {plan['run_seconds']} s", "", "## Evidence", "",
             "| Tool | Transaction | Kind | Target | Observed | Samples | Verdict |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for tool, v in rows:
        observed = "-" if v.observed is None else f"{v.observed:g}"
        lines.append(f"| {tool} | {v.transaction} | {v.kind} | {v.target:g} | {observed} | {v.samples} | {v.status} |")
    lines += ["", "## Tool agreement", ""]
    if agreement:
        lines += [f"- {tx} [{kind}]: {state}" for (tx, kind), state in sorted(agreement.items())]
    else:
        lines.append("- only one tool ran, so there is nothing to compare")
    lines += ["", "## Caveats", ""] + [f"- {c}" for c in caveats] + [""]
    return "\n".join(lines)
