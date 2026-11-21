"""Reading the status codes of a payment load run before reading any latency (no imports needed).

``rows`` are ``{"status": int or None, "headers": {...}}`` for requests to ``POST /v1/payments``; header names may be
in any capitalisation and ``status`` is ``None`` when no answer arrived.

1. ``classify(status, headers=None)`` returns one of ``CLASSES``:
   ``"no-response"`` (status None), ``"replay"`` (2xx with ``Idempotent-Replayed: true``), ``"ok"`` (any other
   2xx), ``"rate-limited"`` (429), ``"overloaded"`` (503), ``"server-error"`` (any other 5xx), ``"auth"`` (401 and
   403), ``"bad-request"`` (any other 4xx), ``"other"`` (anything else).
2. ``summarise(rows)`` returns ``{class: count}`` with EVERY class from ``CLASSES`` present, zeros included.
3. ``verdict(summary, expect_limit=False, script_error_share=0.01, replay_share=0.2)`` returns
   ``{"valid": bool, "findings": [...]}``. ``valid`` is False when the run cannot be read as a measurement of the
   payment API. Findings are strings starting with the check name, in this order:
   - no requests at all: ``"empty: no requests"`` and valid False (stop here);
   - ``"script-error: ..."`` when ``auth`` + ``bad-request`` is more than ``script_error_share`` of all requests
     (valid False);
   - ``"replays: ..."`` when ``replay`` is more than ``replay_share`` of ``ok + replay`` (valid False);
   - ``"rate-limited: ..."`` when any 429 came back and ``expect_limit`` is False (valid False);
   - ``"overloaded: ..."`` when any 503 came back (a result, valid unchanged);
   - ``"server-errors: ..."`` when ``server-error`` + ``no-response`` is more than 1 % of all requests (valid
     unchanged).
   A clean run has ``{"valid": True, "findings": []}``.
"""

from __future__ import annotations

CLASSES = ("ok", "replay", "rate-limited", "overloaded", "server-error", "auth", "bad-request",
           "no-response", "other")


def classify(status, headers=None):
    if status is None:
        return "no-response"
    if 200 <= status < 300:
        replayed = any(k.lower() == "idempotent-replayed" and str(v).lower() == "true"
                       for k, v in (headers or {}).items())
        return "replay" if replayed else "ok"
    if status == 429:
        return "rate-limited"
    if status == 503:
        return "overloaded"
    if 500 <= status < 600:
        return "server-error"
    if status in (401, 403):
        return "auth"
    if 400 <= status < 500:
        return "bad-request"
    return "other"


def summarise(rows):
    counts = {c: 0 for c in CLASSES}
    for row in rows:
        counts[classify(row["status"], row.get("headers"))] += 1
    return counts


def verdict(summary, expect_limit=False, script_error_share=0.01, replay_share=0.2):
    total = sum(summary.values())
    if total == 0:
        return {"valid": False, "findings": ["empty: no requests"]}
    valid, findings = True, []
    rejected = summary["auth"] + summary["bad-request"]
    if rejected / total > script_error_share:
        valid = False
        findings.append(f"script-error: {rejected} of {total} requests were rejected as unauthorised or invalid")
    paid = summary["ok"] + summary["replay"]
    if paid and summary["replay"] / paid > replay_share:
        valid = False
        findings.append(f"replays: {summary['replay']} of {paid} successful requests were idempotent replays")
    if summary["rate-limited"] and not expect_limit:
        valid = False
        findings.append(f"rate-limited: {summary['rate-limited']} requests were answered 429")
    if summary["overloaded"]:
        findings.append(f"overloaded: {summary['overloaded']} requests were answered 503")
    failures = summary["server-error"] + summary["no-response"]
    if failures / total > 0.01:
        findings.append(f"server-errors: {failures} of {total} requests got a 5xx or no answer")
    return {"valid": valid, "findings": findings}
