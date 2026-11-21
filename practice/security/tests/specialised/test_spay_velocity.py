"""Checks exercises/specialised/spay_velocity.py: a card-testing window rule and a velocity-limit probe."""

import copy

import pytest
import spay_fixture as fx
from specialised.spay_velocity import Suspect, detect_card_testing, probe_velocity_limit

pytestmark = pytest.mark.exercise


def test_a_fast_card_tester_is_found_with_the_numbers_of_its_first_window():
    events = fx.tester_events("ip_9", start=100, count=40)
    assert detect_card_testing(events) == [Suspect("ip_9", 100, 30, 30, 27)]


def test_ordinary_shoppers_are_not_suspects():
    events = []
    for n in range(8):
        events += fx.shopper_events(f"ip_{n}", start=n * 50, count=10)
    assert detect_card_testing(events) == []


def test_a_busy_but_honest_merchant_is_not_a_suspect():
    assert detect_card_testing(fx.busy_merchant_events("m_100", 0, 120)) == []


def test_a_slow_tester_is_missed_by_a_one_minute_window_and_found_by_a_longer_one():
    slow = fx.tester_events("ip_slow", start=0, count=40, step=20)
    assert detect_card_testing(slow) == []
    (suspect,) = detect_card_testing(slow, window_s=300, min_decline_ratio=0.6)
    assert suspect.client == "ip_slow" and suspect.attempts >= 10


def test_the_window_is_half_open():
    just_in = [{"t": 6 * i, "client": "c", "card": f"k{i}", "outcome": "declined", "amount_minor": 100} for i in range(10)]
    just_out = [{"t": 7 * i, "client": "c", "card": f"k{i}", "outcome": "declined", "amount_minor": 100} for i in range(10)]
    assert len(detect_card_testing(just_in)) == 1
    assert detect_card_testing(just_out) == []


def test_each_condition_is_needed():
    base = fx.tester_events("c", start=0, count=20)
    one_card = [dict(e, card="same") for e in base]
    assert detect_card_testing(base) != []
    assert detect_card_testing(one_card) == []  # many attempts, one card: a retry loop, not card testing
    approved = [dict(e, outcome="approved") for e in base]
    assert detect_card_testing(approved) == []  # nothing declined
    few = base[:9]
    assert detect_card_testing(few) == []


def test_the_thresholds_are_parameters():
    base = fx.tester_events("c", start=0, count=6)
    assert detect_card_testing(base) == []
    assert len(detect_card_testing(base, min_attempts=5, min_cards=4)) == 1


def test_suspects_are_sorted_by_client_and_events_may_arrive_in_any_order():
    events = fx.tester_events("zz", 0, 30) + fx.tester_events("aa", 500, 30) + fx.shopper_events("mm", 0, 5)
    events.reverse()
    assert [s.client for s in detect_card_testing(events)] == ["aa", "zz"]


def test_the_input_is_not_modified():
    events = fx.tester_events("c", 0, 30)
    events.reverse()
    before = copy.deepcopy(events)
    detect_card_testing(events)
    assert events == before


def test_a_bad_window_or_minimum_is_rejected():
    with pytest.raises(ValueError):
        detect_card_testing([], window_s=0)
    with pytest.raises(ValueError):
        detect_card_testing([], min_attempts=0)


def test_no_events_means_no_suspects():
    assert detect_card_testing([]) == []


def test_the_probe_finds_no_limit_on_a_gateway_without_one():
    gateway = fx.CardGateway()
    assert probe_velocity_limit(gateway, max_attempts=20) is None
    assert gateway.export_records() == []  # nothing was approved


def test_the_probe_finds_the_limit_on_a_fixed_gateway():
    gateway = fx.CardGateway(fixed={"no-velocity"})
    assert probe_velocity_limit(gateway) == fx.VELOCITY_LIMIT + 1


def test_the_limit_is_per_client():
    gateway = fx.CardGateway(fixed={"no-velocity"})
    assert probe_velocity_limit(gateway, client="a") == fx.VELOCITY_LIMIT + 1
    assert probe_velocity_limit(gateway, client="b") == fx.VELOCITY_LIMIT + 1


def test_a_probe_that_gets_an_approval_or_an_odd_status_is_an_error():
    gateway = fx.CardGateway()
    gateway.authorize = lambda *args, **kwargs: (200, {"status": "approved"})
    with pytest.raises(RuntimeError):
        probe_velocity_limit(gateway)
    gateway.authorize = lambda *args, **kwargs: (500, {"error": "boom"})
    with pytest.raises(RuntimeError):
        probe_velocity_limit(gateway)


def test_a_tripped_limit_also_blocks_a_real_card_until_the_client_changes():
    gateway = fx.CardGateway(fixed={"no-velocity"})
    probe_velocity_limit(gateway, client="shared-ip")
    card = gateway.test_cards[0]
    status, _ = gateway.authorize("m_100", "shared-ip", card["pan"], card["expiry"], card["cvv"], 500)
    assert status == 429  # the cost of a per-client limit: an honest customer behind the same address waits
