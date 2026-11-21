"""SOLUTION - Send requests together and decide whether a check-then-act rule survives concurrency.

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
    barrier = threading.Barrier(n)
    results: list = [None] * n

    def worker(index: int) -> None:
        barrier.wait(timeout=5)
        results[index] = call()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    return results


def probe_race(make_desk: Callable[[], RefundDesk], workers: int = 2) -> RaceResult:
    if workers < 2:
        raise ValueError("a race needs at least two requests")
    control = make_desk()
    first, _ = control.refund(PAYMENT, CAPTURED)
    second, _ = control.refund(PAYMENT, CAPTURED)
    if first != 200:
        raise RuntimeError(f"control failed: the first full refund returned {first}")
    if second == 200:
        raise RuntimeError("the second sequential refund already works - that is a double-refund flaw, not a race")
    desk = make_desk()
    results = fire_together(lambda: desk.refund(PAYMENT, CAPTURED), workers)
    statuses = sorted(status for status, _ in results)
    refunded = desk.total_refunded(PAYMENT)
    return RaceResult(refunded > CAPTURED, statuses, refunded, CAPTURED)
