import pytest
from genai.llm_stream import Assembled, StreamError, assemble, events_from_reply, stream_text
from llm_fake import ScriptedLLM

pytestmark = pytest.mark.exercise

ASK = [{"role": "user", "content": "Explain a chargeback in one sentence."}]
ANSWER = "A chargeback is a card payment reversed by the issuing bank after a cardholder dispute."


def reply_for(text=ANSWER, **kwargs):
    return ScriptedLLM([text]).create(messages=ASK, **kwargs)


def test_assembles_text_stop_reason_and_usage():
    reply = reply_for()
    result = assemble(events_from_reply(reply))
    assert isinstance(result, Assembled)
    assert result.text == reply.text
    assert result.stop_reason == "end_turn"
    assert (result.input_tokens, result.output_tokens) == (reply.input_tokens, reply.output_tokens)


def test_usage_is_cumulative_not_summed():
    reply = reply_for()
    events = events_from_reply(reply)
    deltas = [e for e in events if e["type"] == "message_delta"]
    assert len(deltas) == 2  # an early cumulative count and the final one
    assert assemble(events).output_tokens == reply.output_tokens


def test_ignores_pings_and_unknown_events():
    reply = reply_for()
    events = events_from_reply(reply)
    events.insert(2, {"type": "something_new", "data": 1})
    events.insert(4, {"type": "ping"})
    assert assemble(events).text == reply.text


def test_truncated_reply_keeps_max_tokens_stop_reason():
    reply = reply_for(max_tokens=5)
    result = assemble(events_from_reply(reply))
    assert result.stop_reason == "max_tokens" and result.text == "A chargeback is a card"


def test_error_event_raises_with_partial_text():
    events = events_from_reply(reply_for(), fail_after=3)
    with pytest.raises(StreamError) as err:
        assemble(events)
    assert err.value.partial == ANSWER[:12]
    assert "overloaded_error" in str(err.value)


def test_stream_without_message_stop_is_incomplete():
    events = events_from_reply(reply_for())[:-1]
    with pytest.raises(StreamError) as err:
        assemble(events)
    assert err.value.partial == ANSWER


def test_assemble_accepts_a_generator():
    events = events_from_reply(reply_for())
    assert assemble(e for e in events).text == ANSWER


def test_stream_text_calls_back_per_chunk():
    seen: list[str] = []
    llm = ScriptedLLM([ANSWER])
    text = stream_text(llm, seen.append, messages=ASK, max_tokens=100)
    assert text == ANSWER
    assert len(seen) > 5 and "".join(seen) == ANSWER
    assert llm.calls[0].max_tokens == 100
