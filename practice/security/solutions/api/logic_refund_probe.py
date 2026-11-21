"""SOLUTION - Abuse-case probe for a refund service: three business rules, each with a control and no false positive.

``probe_refunds`` runs one abuse case per rule on a different payment, so the cases cannot disturb each other:

| flaw id             | payment | abuse case                                              | the rule it tests               |
| ------------------- | ------- | ------------------------------------------------------- | ------------------------------- |
| ``double-refund``   | p_1     | refund the full captured amount twice                   | refunds add up to at most the capture |
| ``state-bypass``    | p_2     | refund a payment that was declined                      | only captured payments are refunded   |
| ``negative-amount`` | p_3     | refund -500                                             | the amount is a positive integer      |

A control comes first: a normal refund of 1000 on ``p_4`` must work, or "refused" would mean nothing.
"""

from __future__ import annotations

from logic_fixture import RefundDesk


def probe_refunds(desk: RefundDesk) -> list[str]:
    status, _ = desk.refund("p_4", 1000)
    if status != 200 or desk.total_refunded("p_4") != 1000:
        raise RuntimeError(f"control failed: a normal refund of 1000 returned {status}")
    found = []
    first, _ = desk.refund("p_1", 5000)
    if first != 200:
        raise RuntimeError(f"control failed: the first full refund of p_1 returned {first}")
    second, _ = desk.refund("p_1", 5000)
    if second == 200:
        found.append("double-refund")
    declined, _ = desk.refund("p_2", 1000)
    if declined == 200:
        found.append("state-bypass")
    negative, _ = desk.refund("p_3", -500)
    if negative == 200:
        found.append("negative-amount")
    return sorted(found)
