"""Retrying a payment safely under load: one key per logical payment, reused by every retry (no imports needed).

A load script that creates payments has to answer three questions the exercise asks you to write down in code:

1. ``new_key()`` - a fresh Idempotency-Key for every LOGICAL payment: a random version 4 UUID as a string.
2. ``retry_wait(status, headers, attempt)`` - after an attempt that ended with ``status`` (``None`` means no answer
   arrived: a timeout or a dropped connection), say how long to wait before the next attempt, or return ``None``
   when the script must not retry.
   - 2xx: ``None`` (it worked, a replay included).
   - 4xx other than 429: ``None`` (the request itself is wrong; retrying repeats the mistake).
   - ``None``, 429 and 5xx: retry. If the response has a ``Retry-After`` header (any capitalisation) whose value is
     a whole number of seconds, wait that long; otherwise use the back-off ``0.05 * 2 ** (attempt - 1)`` seconds.
     ``attempt`` is the number of attempts already made (1 after the first). Never wait more than ``MAX_WAIT_S``:
     a test run has to stay short (a real script would honour the header in full).
3. ``submit_payment(send, logical, sleep=time.sleep, max_attempts=4)`` - make ONE key, then call ``send(key)`` until
   it works or the rules above say stop. ``send(key)`` returns ``(status, headers)`` and may raise
   ``TimeoutError``, which counts as ``status=None``. Wait with ``sleep(seconds)`` between attempts (not after the
   last one). Return the ledger record
   ``{"logical": logical, "attempts": [{"key", "status", "replayed"}, ...], "outcome": ...}`` where ``replayed``
   is true when the response had ``Idempotent-Replayed: true`` and ``outcome`` is ``"ok"`` (a 2xx came back),
   ``"rejected"`` (a non-retryable status came back) or ``"gave-up"`` (the attempts ran out).
   Every attempt of one logical payment carries the SAME key.
"""

from __future__ import annotations

import time
import uuid

MAX_WAIT_S = 0.1


def new_key():
    raise NotImplementedError("TODO: a random version 4 UUID as a string")


def retry_wait(status, headers, attempt):
    raise NotImplementedError("TODO: None when not retryable, else the Retry-After or back-off seconds, capped")


def submit_payment(send, logical, sleep=time.sleep, max_attempts=4):
    raise NotImplementedError("TODO: one key, send(key) until it works or must stop, return the ledger record")
