"""EXERCISE - Send requests together and decide whether a check-then-act rule survives concurrency.

``fire_together`` releases ``n`` copies of one call at the same moment (a ``threading.Barrier``) and returns their
results. ``probe_race`` uses it against a refund desk: a payment captured for 2500 is refunded in full by
``workers`` requests at once, and the total refunded is compared with the capture.

Before the race test, a SEQUENTIAL control on a fresh desk: the second full refund must already be refused. If it is
not, the rule is simply missing (a double-refund flaw) and there is nothing to learn from a race.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

from logic_fixture import RefundDesk

PAYMENT = "p_4"
CAPTURED = 2500


@dataclass(frozen=True)
class RaceResult:
    vulnerable: bool
    statuses: list[int]   # sorted statuses of the concurrent refunds
    refunded: int         # total refunded on the payment afterwards
    captured: int


def fire_together(call: Callable[[], object], n: int) -> list:
    """Run ``call()`` in ``n`` threads that all start at the same moment and return the ``n`` results in thread order.

    Use a ``threading.Barrier(n)``: every thread waits on it, then calls. Join every thread before returning.
    """
    raise NotImplementedError("TODO: implement fire_together")


def probe_race(make_desk: Callable[[], RefundDesk], workers: int = 2) -> RaceResult:
    """Decide whether the refund rule survives ``workers`` simultaneous full refunds of ``PAYMENT``.

    1. Raise ``ValueError`` when ``workers`` < 2.
    2. Control on a fresh desk (``make_desk()``): two SEQUENTIAL full refunds. Raise ``RuntimeError`` if the first
       is not 200, or if the second is 200 (then it is a double-refund flaw, not a race).
    3. On another fresh desk, fire ``workers`` full refunds together with ``fire_together``.
    4. ``vulnerable`` is true when the total refunded is more than ``CAPTURED``.
    """
    raise NotImplementedError("TODO: implement probe_race")
