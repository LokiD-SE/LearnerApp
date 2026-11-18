from decimal import Decimal

import pytest
from llm_fake import ScriptedLLM
from production.ops_cost import BudgetExceeded, BudgetGuard, Price, ResponseCache, request_cost, request_key

pytestmark = pytest.mark.exercise

SMALL = Price(Decimal("1"), Decimal("5"))


class Clock:
    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now


def test_cost_of_plain_request():
    assert request_cost(SMALL, input_tokens=2_000, output_tokens=400) == Decimal("0.004")


def test_cost_uses_cache_multipliers():
    cost = request_cost(SMALL, input_tokens=100, output_tokens=200, cache_write_tokens=4_000, cache_read_tokens=0)
    assert cost == Decimal("0.0001") + Decimal("0.005") + Decimal("0.001")
    reread = request_cost(SMALL, input_tokens=100, output_tokens=200, cache_read_tokens=4_000)
    assert reread == Decimal("0.0001") + Decimal("0.0004") + Decimal("0.001")


def test_cost_is_decimal_not_float():
    assert isinstance(request_cost(SMALL, input_tokens=1, output_tokens=1), Decimal)


def test_cost_rejects_negative_counts():
    with pytest.raises(ValueError):
        request_cost(SMALL, input_tokens=-1, output_tokens=0)


def test_request_key_ignores_key_order_but_not_content():
    a = {"model": "m", "temperature": 0, "messages": [{"role": "user", "content": "hi"}]}
    b = {"messages": [{"content": "hi", "role": "user"}], "temperature": 0, "model": "m"}
    c = {"model": "m", "temperature": 0, "messages": [{"role": "user", "content": "hi!"}]}
    assert request_key(a) == request_key(b)
    assert request_key(a) != request_key(c)
    assert len(request_key(a)) == 64


def make_cache(clock, **kw):
    return ResponseCache(max_entries=kw.get("max_entries", 2), ttl=kw.get("ttl", 60), clock=clock)


def req(text, temperature=0):
    return {"messages": [{"role": "user", "content": text}], "max_tokens": 50, "temperature": temperature}


def test_cache_hit_on_identical_request():
    clock = Clock()
    llm = ScriptedLLM(["Refunds take 5-10 business days."])
    cache = make_cache(clock)
    first, cached1 = cache.get_or_call(req("How long do refunds take?"), lambda r: llm.create(**r))
    second, cached2 = cache.get_or_call(req("How long do refunds take?"), lambda r: llm.create(**r))
    assert (cached1, cached2) == (False, True)
    assert second is first
    assert len(llm.calls) == 1
    assert (cache.hits, cache.misses, cache.hit_rate) == (1, 1, 0.5)


def test_sampled_requests_are_never_cached():
    llm = ScriptedLLM(["a", "b"])
    cache = make_cache(Clock())
    cache.get_or_call(req("hi", temperature=0.7), lambda r: llm.create(**r))
    _, cached = cache.get_or_call(req("hi", temperature=0.7), lambda r: llm.create(**r))
    assert cached is False
    assert len(llm.calls) == 2
    assert (cache.hits, cache.misses) == (0, 0)


def test_cut_off_replies_are_not_stored():
    llm = ScriptedLLM(["one two three four five six", "one two three four five six"])
    cache = make_cache(Clock())
    short = {"messages": [{"role": "user", "content": "count"}], "max_tokens": 2, "temperature": 0}
    first, _ = cache.get_or_call(short, lambda r: llm.create(**r))
    assert first.stop_reason == "max_tokens"
    _, cached = cache.get_or_call(short, lambda r: llm.create(**r))
    assert cached is False
    assert len(llm.calls) == 2


def test_entries_expire_after_ttl():
    clock = Clock()
    llm = ScriptedLLM(["old answer", "new answer"])
    cache = make_cache(clock, ttl=60)
    cache.get_or_call(req("fees?"), lambda r: llm.create(**r))
    clock.now = 59.9
    assert cache.get_or_call(req("fees?"), lambda r: llm.create(**r))[1] is True
    clock.now = 120
    reply, cached = cache.get_or_call(req("fees?"), lambda r: llm.create(**r))
    assert cached is False
    assert reply.text == "new answer"


def test_least_recently_used_entry_is_evicted():
    llm = ScriptedLLM(lambda r: "answer to " + r.messages[-1]["content"])
    cache = make_cache(Clock(), max_entries=2)
    call = lambda r: llm.create(**r)  # noqa: E731
    cache.get_or_call(req("a"), call)
    cache.get_or_call(req("b"), call)
    cache.get_or_call(req("a"), call)  # a is now most recent
    cache.get_or_call(req("c"), call)  # evicts b
    assert cache.get_or_call(req("a"), call)[1] is True
    assert cache.get_or_call(req("b"), call)[1] is False


def test_cache_rejects_bad_settings():
    with pytest.raises(ValueError):
        ResponseCache(max_entries=0, ttl=60, clock=Clock())
    with pytest.raises(ValueError):
        ResponseCache(max_entries=10, ttl=0, clock=Clock())


def make_guard(clock, **kw):
    settings = dict(max_input_tokens=8_000, max_output_tokens=1_000, burst=2, refill_per_second=0.5, daily_budget=Decimal("1.00"), clock=clock)
    settings.update(kw)
    return BudgetGuard(**settings)


def ok_check(guard, user="m-204", cost="0.01", input_tokens=500, max_tokens=300):
    guard.check(user, input_tokens=input_tokens, max_tokens=max_tokens, estimated_cost=Decimal(cost))


def test_guard_refuses_oversized_input_and_output_caps():
    guard = make_guard(Clock())
    with pytest.raises(BudgetExceeded) as info:
        ok_check(guard, input_tokens=8_001)
    assert info.value.reason == "input_too_large"
    with pytest.raises(BudgetExceeded) as info:
        ok_check(guard, max_tokens=4_096)
    assert info.value.reason == "max_tokens_too_high"


def test_guard_token_bucket_per_user():
    clock = Clock()
    guard = make_guard(clock)
    ok_check(guard)
    ok_check(guard)
    with pytest.raises(BudgetExceeded) as info:
        ok_check(guard)
    assert info.value.reason == "rate_limited"
    ok_check(guard, user="m-311")  # another merchant has its own bucket
    clock.now = 2.0  # 2 s * 0.5/s = one request refilled
    ok_check(guard)
    with pytest.raises(BudgetExceeded):
        ok_check(guard)


def test_guard_bucket_never_exceeds_burst():
    clock = Clock()
    guard = make_guard(clock)
    clock.now = 3600
    ok_check(guard)
    ok_check(guard)
    with pytest.raises(BudgetExceeded):
        ok_check(guard)


def test_guard_daily_budget_and_reset():
    clock = Clock(100.0)
    guard = make_guard(clock, burst=100)
    guard.record(Decimal("0.95"))
    ok_check(guard, cost="0.05")
    with pytest.raises(BudgetExceeded) as info:
        ok_check(guard, cost="0.06")
    assert info.value.reason == "daily_budget"
    clock.now = 86_400 + 5
    ok_check(guard, cost="0.06")
    assert guard.spent == Decimal(0)


def test_refused_request_does_not_use_a_bucket_token():
    clock = Clock()
    guard = make_guard(clock, burst=1)
    guard.record(Decimal("1.00"))
    with pytest.raises(BudgetExceeded):
        ok_check(guard, cost="0.01")
    clock.now = 86_400  # new day; the bucket still holds its one token
    ok_check(guard)
