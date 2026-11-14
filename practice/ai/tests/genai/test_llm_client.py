import pytest
from genai.llm_client import TOY_PRICES, LLMClient, backoff_delay, cost_usd, is_retryable
from llm_fake import BadRequestError, OverloadedError, RateLimitError, ScriptedLLM

pytestmark = pytest.mark.exercise

HI = [{"role": "user", "content": "Where is my refund?"}]


def make(script, **kwargs):
    slept: list[float] = []
    llm = ScriptedLLM(script)
    client = LLMClient(llm, "toy-small", sleep=slept.append, rand=lambda: 0.5, **kwargs)
    return llm, client, slept


def test_backoff_grows_exponentially_and_is_capped():
    assert [backoff_delay(a, 0.5, 8.0, lambda: 0.999) for a in range(6)] == pytest.approx(
        [0.4995, 0.999, 1.998, 3.996, 7.992, 7.992]
    )
    assert backoff_delay(3, 0.5, 8.0, lambda: 0.0) == 0.0  # full jitter can be zero
    with pytest.raises(ValueError):
        backoff_delay(-1, 0.5, 8.0, lambda: 0.5)


def test_retryable_errors():
    assert is_retryable(RateLimitError(2)) and is_retryable(OverloadedError())
    assert not is_retryable(BadRequestError("bad"))
    assert not is_retryable(ValueError("not an API error"))

    class Overloaded529(Exception):
        status = 529

    class NotFound(Exception):
        status = 404

    assert is_retryable(Overloaded529()) and not is_retryable(NotFound())


def test_honours_retry_after_then_backs_off():
    llm, client, slept = make([RateLimitError(retry_after=3), OverloadedError(), OverloadedError(), "Refund sent."])
    reply = client.create(messages=HI, max_tokens=50)
    assert reply.text == "Refund sent."
    # retry_after 3 plus jitter 0.5 * base; then full jitter 0.5 * 0.5 * 2**1 and 0.5 * 0.5 * 2**2
    assert slept == pytest.approx([3.25, 0.5, 1.0])
    assert len(llm.calls) == 4 and client.waits == pytest.approx(slept)


def test_never_waits_less_than_retry_after():
    _, client, slept = make([RateLimitError(retry_after=5)] * 2 + ["ok"], base=0.1)
    client.rand = lambda: 0.0
    client.create(messages=HI)
    assert all(wait >= 5 for wait in slept)


def test_bad_request_is_not_retried():
    llm, client, slept = make([BadRequestError("max_tokens too large"), "never sent"])
    with pytest.raises(BadRequestError):
        client.create(messages=HI)
    assert len(llm.calls) == 1 and slept == []


def test_gives_up_after_max_retries():
    llm, client, slept = make([OverloadedError()] * 10, max_retries=2)
    with pytest.raises(OverloadedError):
        client.create(messages=HI)
    assert len(llm.calls) == 3 and len(slept) == 2


def test_stops_when_wait_budget_would_be_exceeded():
    llm, client, slept = make([RateLimitError(retry_after=20), RateLimitError(retry_after=20), "ok"], max_total_wait=30)
    with pytest.raises(RateLimitError):
        client.create(messages=HI)
    assert len(llm.calls) == 2 and slept == pytest.approx([20.25])


def test_cost_and_usage_accounting():
    assert cost_usd(1_000_000, 0, "toy-small", TOY_PRICES) == pytest.approx(0.5)
    assert cost_usd(2000, 500, "toy-large", TOY_PRICES) == pytest.approx(0.0225)
    with pytest.raises(KeyError):
        cost_usd(1, 1, "no-such-model", TOY_PRICES)

    llm, client, _ = make([RateLimitError(1), "Your refund of 12.50 EUR was sent.", "Done."])
    first = client.create(messages=HI)
    second = client.create(messages=HI)
    assert client.calls == 2  # the rate-limited attempt is not a billed call
    assert client.input_tokens == first.input_tokens + second.input_tokens
    assert client.output_tokens == first.output_tokens + second.output_tokens == 10 + 2
    expected = cost_usd(client.input_tokens, client.output_tokens, "toy-small", TOY_PRICES)
    assert client.cost == pytest.approx(expected)
