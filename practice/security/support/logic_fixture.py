"""Shared pieces for the business logic lesson (Track L, testing-business-logic-and-rate-limits).

``RefundDesk`` is a tiny, in-process model of SandPay's refund service. The portal in ``sandpay_vuln.py`` has no
refund endpoint, so this fixture holds the logic flaws the lesson needs. It opens no socket and sends nothing.
Everything is synthetic.

Each flaw has an id. ``RefundDesk(fixed={...})`` fixes those flaws, exactly like ``make_app(fixed=...)``:

| flaw id           | rule that is not enforced                                              |
| ----------------- | ---------------------------------------------------------------------- |
| ``double-refund`` | refunds must never add up to more than was captured                    |
| ``state-bypass``  | only a payment in state ``captured`` can be refunded                   |
| ``negative-amount`` | a refund amount must be a positive whole number of minor units       |
| ``race``          | the check "is there enough left?" and the write must be one atomic step |

Seeded payments (amounts in minor units, EUR): ``p_1`` captured 5000, ``p_2`` declined 3000, ``p_3`` captured 4000,
``p_4`` captured 2500. ``refund`` returns ``(status, body)`` like an HTTP handler would.
"""

from __future__ import annotations

import threading
import time

FLAWS = ("double-refund", "state-bypass", "negative-amount", "race")
RACE_WINDOW_S = 0.05  # the gap between "check" and "write" when ``race`` is not fixed


class RefundDesk:
    def __init__(self, fixed=()):
        unknown = set(fixed) - set(FLAWS)
        if unknown:
            raise ValueError(f"unknown flaw ids: {sorted(unknown)}; known: {FLAWS}")
        self.fixed = frozenset(fixed)
        self._lock = threading.Lock()
        self.payments = {
            "p_1": {"status": "captured", "captured": 5000, "refunded": 0},
            "p_2": {"status": "declined", "captured": 3000, "refunded": 0},
            "p_3": {"status": "captured", "captured": 4000, "refunded": 0},
            "p_4": {"status": "captured", "captured": 2500, "refunded": 0},
        }

    def total_refunded(self, payment_id: str) -> int:
        return self.payments[payment_id]["refunded"]

    def refund(self, payment_id: str, amount_minor) -> tuple[int, dict]:
        payment = self.payments.get(payment_id)
        if payment is None:
            return 404, {"error": "payment not found"}
        if "negative-amount" in self.fixed and (type(amount_minor) is not int or amount_minor <= 0):
            return 422, {"error": "amount must be a positive integer"}
        if "state-bypass" in self.fixed and payment["status"] != "captured":
            return 409, {"error": f"cannot refund a payment that is {payment['status']}"}
        if "race" in self.fixed:
            with self._lock:  # check and write are one atomic step
                return self._check_and_write(payment, amount_minor)
        return self._check_and_write(payment, amount_minor)

    def _check_and_write(self, payment: dict, amount_minor) -> tuple[int, dict]:
        # double-refund fixed: compare with what is LEFT; not fixed: compare with the captured total only
        limit = payment["captured"] - payment["refunded"] if "double-refund" in self.fixed else payment["captured"]
        if amount_minor > limit:
            return 409, {"error": "refund is more than the amount left"}
        if "race" not in self.fixed:
            time.sleep(RACE_WINDOW_S)  # the slow part between the check and the write
        payment["refunded"] += amount_minor
        return 200, {"refunded": amount_minor, "total_refunded": payment["refunded"]}
