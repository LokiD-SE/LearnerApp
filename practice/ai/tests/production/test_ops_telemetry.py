import pytest
from llm_fake import OverloadedError, ScriptedLLM
from production.ops_telemetry import RunSummary, Tracer, percentile, release_gate, time_to_first_chunk, traced_chat

pytestmark = pytest.mark.exercise


class TickClock:
    """Each read advances time by ``step`` seconds."""

    def __init__(self, step=0.25):
        self.now = 0.0
        self.step = step

    def __call__(self):
        value = self.now
        self.now += self.step
        return value


def test_successful_call_span_name_and_attributes():
    tracer = Tracer(TickClock())
    llm = ScriptedLLM(["Your payout po_204 is scheduled."])
    reply = traced_chat(
        tracer, llm, provider="anthropic", model="model-small",
        messages=[{"role": "user", "content": "Where is my payout?"}], max_tokens=64, temperature=0,
    )
    assert reply.text.startswith("Your payout")
    [span] = tracer.spans
    assert span.name == "chat model-small"
    assert span.status == "UNSET"
    assert span.attributes["gen_ai.operation.name"] == "chat"
    assert span.attributes["gen_ai.provider.name"] == "anthropic"
    assert span.attributes["gen_ai.request.model"] == "model-small"
    assert span.attributes["gen_ai.request.max_tokens"] == 64
    assert span.attributes["gen_ai.request.temperature"] == 0
    assert span.attributes["gen_ai.usage.input_tokens"] == reply.input_tokens
    assert span.attributes["gen_ai.usage.output_tokens"] == reply.output_tokens
    assert span.attributes["gen_ai.response.finish_reasons"] == ["end_turn"]
    assert span.duration == pytest.approx(0.25)


def test_optional_request_attributes_are_omitted_when_absent():
    tracer = Tracer(TickClock())
    traced_chat(tracer, ScriptedLLM(["ok"]), provider="openai", model="m", messages=[{"role": "user", "content": "hi"}])
    attributes = tracer.spans[0].attributes
    assert "gen_ai.request.max_tokens" not in attributes
    assert "gen_ai.request.temperature" not in attributes


def test_message_content_is_not_recorded():
    tracer = Tracer(TickClock())
    traced_chat(
        tracer, ScriptedLLM(["secret reply"]), provider="anthropic", model="m",
        messages=[{"role": "user", "content": "my email is ana@example.com"}], max_tokens=10,
    )
    flat = repr(tracer.spans[0].attributes)
    assert "ana@example.com" not in flat
    assert "secret reply" not in flat


def test_failed_call_records_error_and_reraises():
    tracer = Tracer(TickClock())
    llm = ScriptedLLM([OverloadedError("busy")])
    with pytest.raises(OverloadedError):
        traced_chat(tracer, llm, provider="anthropic", model="m", messages=[{"role": "user", "content": "hi"}])
    [span] = tracer.spans
    assert span.status == "ERROR"
    assert span.attributes["error.type"] == "OverloadedError"
    assert span.end is not None
    assert "gen_ai.usage.input_tokens" not in span.attributes


def test_cut_off_reply_finish_reason():
    tracer = Tracer(TickClock())
    traced_chat(tracer, ScriptedLLM(["one two three"]), provider="p", model="m", messages=[{"role": "user", "content": "x"}], max_tokens=1)
    assert tracer.spans[0].attributes["gen_ai.response.finish_reasons"] == ["max_tokens"]


def test_time_to_first_chunk_and_total():
    clock = TickClock(0.1)
    start = clock()  # 0.0
    ttfc, total, text = time_to_first_chunk(start, iter(["Hel", "lo", "!"]), clock)
    assert ttfc == pytest.approx(0.1)
    assert total == pytest.approx(0.2)
    assert text == "Hello!"


def test_time_to_first_chunk_skips_empty_chunks_and_handles_no_chunks():
    clock = TickClock(0.1)
    start = clock()
    ttfc, _, text = time_to_first_chunk(start, iter(["", "", "x"]), clock)
    assert ttfc == pytest.approx(0.1)
    assert text == "x"
    ttfc, total, text = time_to_first_chunk(clock(), iter([]), clock)
    assert ttfc is None
    assert text == ""


def test_percentile_nearest_rank():
    values = [1.2, 0.8, 0.9, 1.0, 4.5, 1.1, 0.7, 1.3, 1.0, 9.0]
    assert percentile(values, 50) == 1.0
    assert percentile(values, 90) == 4.5
    assert percentile(values, 95) == 9.0
    assert percentile(values, 100) == 9.0
    assert percentile([3.0], 50) == 3.0


def test_percentile_rejects_bad_input():
    with pytest.raises(ValueError):
        percentile([], 50)
    with pytest.raises(ValueError):
        percentile([1.0], 0)
    with pytest.raises(ValueError):
        percentile([1.0], 101)


def run(passed, latencies=(1.0,) * 20, cost=1.0):
    return RunSummary(passed=dict(passed), latencies=list(latencies), cost=cost)


CASES = {f"g{i:02d}": True for i in range(1, 21)}


def gate(baseline, candidate):
    return release_gate(baseline, candidate, max_pass_rate_drop=0.02, p95_budget=3.0, max_cost_increase=0.2)


def test_identical_runs_ship():
    assert gate(run(CASES), run(CASES)) == []


def test_single_regressed_case_blocks_even_within_rate_tolerance():
    candidate = dict(CASES, g07=False)
    base = dict(CASES, g19=False)
    reasons = gate(run(base), run(dict(candidate, g19=True)))
    assert reasons == ["regressed: g07"]


def test_pass_rate_drop_reported():
    candidate = dict(CASES, g03=False, g11=False)
    reasons = gate(run(CASES), run(candidate))
    assert reasons == ["pass rate 1.000 -> 0.900", "regressed: g03, g11"]


def test_latency_and_cost_budgets():
    slow = [1.0] * 17 + [2.0, 6.5, 7.0]
    reasons = gate(run(CASES), run(CASES, latencies=slow, cost=1.5))
    assert reasons == ["p95 latency 6.50 > 3.00", "cost +50%"]


def test_cost_within_tolerance_ships():
    assert gate(run(CASES, cost=1.0), run(CASES, cost=1.19)) == []


def test_runs_must_cover_the_same_cases():
    with pytest.raises(ValueError):
        gate(run(CASES), run(dict(CASES, g21=True)))
