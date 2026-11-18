import random

import pytest
from llm_fake import BadRequestError, OverloadedError, RateLimitError, ScriptedLLM
from production.ops_resilience import (
    FallbackChain,
    RetryBudgetExceeded,
    SpendCapError,
    backoff_delay,
    call_with_retries,
    is_retryable,
)

pytestmark = pytest.mark.exercise


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def options(t, **kw):
    base = dict(clock=t.clock, sleep=t.sleep, rng=random.Random(7))
    base.update(kw)
    return base


def flaky(steps):
    """A function that raises or returns the next step each call."""
    calls = {"n": 0}

    def fn():
        step = steps[calls["n"]]
        calls["n"] += 1
        if isinstance(step, Exception):
            raise step
        return step

    fn.calls = calls
    return fn


def test_retryable_classification():
    assert is_retryable(RateLimitError(retry_after=2))
    assert is_retryable(OverloadedError("busy"))
    assert not is_retryable(BadRequestError("bad"))
    assert not is_retryable(SpendCapError("cap"))
    assert not is_retryable(ValueError("not an API error"))


def test_backoff_full_jitter_stays_within_the_capped_window():
    rng = random.Random(1)
    for attempt, ceiling in [(0, 0.5), (1, 1.0), (2, 2.0), (3, 4.0), (6, 8.0), (10, 8.0)]:
        for _ in range(200):
            d = backoff_delay(attempt, 0.5, 8.0, rng)
            assert 0 <= d <= ceiling


def test_backoff_is_random_not_fixed():
    rng = random.Random(3)
    values = {round(backoff_delay(3, 0.5, 8.0, rng), 6) for _ in range(20)}
    assert len(values) > 10


def test_backoff_rejects_negative_attempt():
    with pytest.raises(ValueError):
        backoff_delay(-1, 0.5, 8.0, random.Random(0))


def test_success_first_time_records_one_attempt():
    t = FakeTime()
    result = call_with_retries(flaky(["ok"]), **options(t))
    assert result.value == "ok"
    assert [(a.number, a.error) for a in result.attempts] == [(1, None)]
    assert t.sleeps == []


def test_retries_a_transient_error_then_succeeds():
    t = FakeTime()
    fn = flaky([OverloadedError("busy"), OverloadedError("busy"), "ok"])
    result = call_with_retries(fn, **options(t, max_attempts=3))
    assert result.value == "ok"
    assert [a.error for a in result.attempts] == ["OverloadedError", "OverloadedError", None]
    assert len(t.sleeps) == 2
    assert fn.calls["n"] == 3


def test_waits_at_least_retry_after():
    t = FakeTime()
    fn = flaky([RateLimitError(retry_after=5), "ok"])
    result = call_with_retries(fn, **options(t, base=0.1, cap=1.0))
    assert t.sleeps[0] >= 5
    assert result.attempts[0].waited == t.sleeps[0]


def test_bad_request_is_not_retried():
    t = FakeTime()
    fn = flaky([BadRequestError("max_tokens must be at least 1"), "never"])
    with pytest.raises(BadRequestError):
        call_with_retries(fn, **options(t))
    assert fn.calls["n"] == 1
    assert t.sleeps == []


def test_spend_cap_is_not_retried():
    t = FakeTime()
    fn = flaky([SpendCapError("monthly cap"), "never"])
    with pytest.raises(SpendCapError):
        call_with_retries(fn, **options(t))
    assert fn.calls["n"] == 1


def test_last_error_raised_when_attempts_run_out():
    t = FakeTime()
    fn = flaky([OverloadedError("1"), OverloadedError("2"), OverloadedError("3"), "late"])
    with pytest.raises(OverloadedError, match="3"):
        call_with_retries(fn, **options(t, max_attempts=3))
    assert fn.calls["n"] == 3
    assert len(t.sleeps) == 2


def test_gives_up_instead_of_sleeping_past_the_deadline():
    t = FakeTime()
    fn = flaky([RateLimitError(retry_after=30), "ok"])
    with pytest.raises(RetryBudgetExceeded) as info:
        call_with_retries(fn, **options(t, deadline=10.0))
    assert isinstance(info.value.last_error, RateLimitError)
    assert info.value.attempts == 1
    assert t.sleeps == []


def test_rejects_zero_attempts():
    with pytest.raises(ValueError):
        call_with_retries(lambda: "x", **options(FakeTime(), max_attempts=0))


def test_fallback_uses_second_model_when_first_is_overloaded():
    t = FakeTime()
    primary = ScriptedLLM([OverloadedError("busy")] * 2)
    secondary = ScriptedLLM(["Payout po_204 is scheduled for Friday."])
    chain = FallbackChain([("large", primary), ("small", secondary)], **options(t, max_attempts=2))
    result = chain.create(messages=[{"role": "user", "content": "When is my payout?"}], max_tokens=50)
    assert result.model == "small"
    assert result.reply.text.startswith("Payout po_204")
    assert result.tried == [("large", "OverloadedError"), ("small", "ok")]
    assert len(primary.calls) == 2


def test_fallback_on_spend_cap_without_retrying():
    t = FakeTime()
    primary = ScriptedLLM([SpendCapError("cap")])
    secondary = ScriptedLLM(["ok"])
    chain = FallbackChain([("large", primary), ("small", secondary)], **options(t))
    result = chain.create(messages=[{"role": "user", "content": "hi"}], max_tokens=5)
    assert result.tried == [("large", "SpendCapError"), ("small", "ok")]
    assert len(primary.calls) == 1


def test_no_fallback_for_a_bad_request():
    t = FakeTime()
    primary = ScriptedLLM([BadRequestError("bad schema")])
    secondary = ScriptedLLM(["should not be called"])
    chain = FallbackChain([("large", primary), ("small", secondary)], **options(t))
    with pytest.raises(BadRequestError):
        chain.create(messages=[{"role": "user", "content": "hi"}], max_tokens=5)
    assert secondary.calls == []


def test_all_models_down_raises_the_last_error():
    t = FakeTime()
    chain = FallbackChain(
        [("large", ScriptedLLM([OverloadedError("a")] * 2)), ("small", ScriptedLLM([RateLimitError(retry_after=1)] * 2))],
        **options(t, max_attempts=2),
    )
    with pytest.raises(RateLimitError):
        chain.create(messages=[{"role": "user", "content": "hi"}], max_tokens=5)


def test_fallback_needs_a_model():
    with pytest.raises(ValueError):
        FallbackChain([])
