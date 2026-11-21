"""Checks exercises/api/logic_refund_probe.py: it must find each business rule that is not enforced and report
nothing once the rules are enforced."""

import pytest
from api.logic_refund_probe import probe_refunds
from logic_fixture import RefundDesk

pytestmark = pytest.mark.exercise

SEQUENTIAL = {"double-refund", "state-bypass", "negative-amount"}


def test_finds_all_three_flaws_on_the_vulnerable_desk():
    assert probe_refunds(RefundDesk()) == ["double-refund", "negative-amount", "state-bypass"]


def test_reports_nothing_once_every_rule_is_enforced():
    assert probe_refunds(RefundDesk(SEQUENTIAL)) == []


@pytest.mark.parametrize("flaw", sorted(SEQUENTIAL))
def test_each_case_sees_only_its_own_flaw(flaw):
    assert probe_refunds(RefundDesk(SEQUENTIAL - {flaw})) == [flaw]


def test_the_race_flaw_does_not_change_a_sequential_probe():
    assert probe_refunds(RefundDesk(SEQUENTIAL)) == []


def test_probe_uses_a_harmless_amount_for_the_control():
    desk = RefundDesk(SEQUENTIAL)
    probe_refunds(desk)
    assert desk.total_refunded("p_4") == 1000
    assert desk.total_refunded("p_1") == 5000  # the one legitimate full refund; the second was refused
    assert desk.total_refunded("p_2") == 0 and desk.total_refunded("p_3") == 0


def test_a_failed_control_raises_instead_of_giving_a_verdict():
    class Broken(RefundDesk):
        def refund(self, payment_id, amount_minor):
            return 500, {"error": "down"}

    with pytest.raises(RuntimeError):
        probe_refunds(Broken())
