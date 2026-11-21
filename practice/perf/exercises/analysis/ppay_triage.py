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
    raise NotImplementedError("TODO: one of CLASSES for a status and its headers")


def summarise(rows):
    raise NotImplementedError("TODO: a count for every class, zeros included")


def verdict(summary, expect_limit=False, script_error_share=0.01, replay_share=0.2):
    raise NotImplementedError("TODO: valid flag and findings in the documented order")
