"""Checks the shared offline helpers (not a learner exercise, so no ``exercise`` marker)."""

import numpy as np
import pytest
from llm_fake import BadRequestError, RateLimitError, ScriptedLLM, count_tokens
from toy_embeddings import embed, embed_many


def test_scripted_replies_tools_errors_and_limits():
    llm = ScriptedLLM(["Hello there, friend.", {"tool": "lookup", "input": {"id": 7}}, RateLimitError(2), "one two three"])
    reply = llm.create(messages=[{"role": "user", "content": "hi"}])
    assert (reply.text, reply.stop_reason, reply.output_tokens) == ("Hello there, friend.", "end_turn", 5)
    tool = llm.create(messages=[{"role": "user", "content": "find 7"}])
    assert tool.stop_reason == "tool_use" and tool.tool_calls[0]["input"] == {"id": 7}
    with pytest.raises(RateLimitError) as err:
        llm.create(messages=[{"role": "user", "content": "again"}])
    assert err.value.retry_after == 2 and err.value.retryable
    cut = llm.create(messages=[{"role": "user", "content": "count"}], max_tokens=2)
    assert (cut.text, cut.stop_reason) == ("one two", "max_tokens")
    assert len(llm.calls) == 4
    with pytest.raises(AssertionError):
        llm.create(messages=[{"role": "user", "content": "more"}])
    with pytest.raises(BadRequestError):
        ScriptedLLM(["x"]).create(messages=[])


def test_callable_script_and_stream():
    llm = ScriptedLLM(lambda req: req.messages[-1]["content"].upper())
    assert "".join(llm.stream(messages=[{"role": "user", "content": "refund please"}])) == "REFUND PLEASE"
    assert count_tokens("Refund 12.50, please!") == 7


def test_toy_embeddings():
    a, b, c = embed_many(["refund my card payment", "refund the card payment", "weather in Paris today"])
    assert np.isclose(np.linalg.norm(a), 1.0)
    assert a @ b > 0.4 > abs(a @ c)
    np.testing.assert_array_equal(embed("Refund"), embed("refund"))
