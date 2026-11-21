"""EXERCISE - Abuse-case probe for a refund service: three business rules, each with a control and no false positive.

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
    """Return the sorted flaw ids the desk shows (a subset of the three in the table).

    Control first: refund 1000 on ``p_4`` and check the status is 200 and ``desk.total_refunded("p_4") == 1000``;
    raise ``RuntimeError`` otherwise. For ``double-refund`` the FIRST full refund of ``p_1`` must be 200 (raise
    ``RuntimeError`` if not) and the SECOND must be refused; a 200 there is the finding. Then the other two cases.
    A case is a finding only when the answer is exactly 200.
    """
    raise NotImplementedError("TODO: implement probe_refunds")
