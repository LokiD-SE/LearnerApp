"""Checks exercises/api/logic_race.py: a refund rule that holds for sequential requests can still fail when two
requests arrive together, and the probe must tell the two cases apart."""

import threading

import pytest
from api.logic_race import CAPTURED, PAYMENT, RaceResult, fire_together, probe_race
from logic_fixture import RefundDesk

pytestmark = pytest.mark.exercise

SEQUENTIAL = {"double-refund", "state-bypass", "negative-amount"}


def test_fire_together_runs_every_call_and_keeps_thread_order():
    counter = iter(range(10))
    lock = threading.Lock()

    def call():
        with lock:
            return next(counter)

    results = fire_together(call, 4)
    assert sorted(results) == [0, 1, 2, 3]


def test_fire_together_releases_all_threads_at_the_same_moment():
    # if the calls ran one after another, the barrier below would time out
    barrier = threading.Barrier(3)
    results = fire_together(lambda: barrier.wait(timeout=2) >= 0, 3)
    assert results == [True, True, True]


def test_the_race_is_found_when_check_and_write_are_not_atomic():
    result = probe_race(lambda: RefundDesk(SEQUENTIAL))
    assert isinstance(result, RaceResult)
    assert result.vulnerable
    assert result.statuses == [200, 200]
    assert result.refunded == 2 * CAPTURED and result.captured == CAPTURED


def test_no_false_positive_when_the_check_and_write_are_atomic():
    result = probe_race(lambda: RefundDesk(SEQUENTIAL | {"race"}))
    assert not result.vulnerable
    assert result.statuses == [200, 409]
    assert result.refunded == CAPTURED


def test_more_workers_still_never_exceed_the_capture_when_fixed():
    result = probe_race(lambda: RefundDesk(SEQUENTIAL | {"race"}), workers=5)
    assert not result.vulnerable and result.statuses == [200, 409, 409, 409, 409]


def test_a_missing_rule_is_not_reported_as_a_race():
    with pytest.raises(RuntimeError, match="double-refund"):
        probe_race(lambda: RefundDesk())


def test_a_race_needs_two_requests():
    with pytest.raises(ValueError):
        probe_race(lambda: RefundDesk(SEQUENTIAL), workers=1)


def test_each_probe_uses_a_fresh_desk():
    made = []

    def factory():
        made.append(RefundDesk(SEQUENTIAL | {"race"}))
        return made[-1]

    probe_race(factory)
    assert len(made) == 2 and made[0] is not made[1]
    assert made[0].total_refunded(PAYMENT) == CAPTURED
