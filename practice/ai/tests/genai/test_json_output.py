import pytest
from genai.json_output import TRIAGE_INSTRUCTIONS, StructuredOutputError, extract_json, triage, validate_triage
from llm_fake import ScriptedLLM

pytestmark = pytest.mark.exercise

TICKET = "I was charged 42.10 EUR twice at Cafe Lumen yesterday, please refund one of them!"
GOOD = '{"category": "refund", "amount": 42.10, "currency": "EUR", "urgent": false, "summary": "Double charge at Cafe Lumen."}'
CLEAN = {"category": "refund", "amount": 42.1, "currency": "EUR", "urgent": False, "summary": "Double charge at Cafe Lumen."}


def test_extract_bare_fenced_and_wrapped_json():
    assert extract_json(GOOD) == extract_json("```json\n" + GOOD + "\n```") == extract_json("Sure! " + GOOD + " Hope it helps.")
    with pytest.raises(ValueError):
        extract_json("I cannot help with that.")
    with pytest.raises(ValueError):
        extract_json('{"category": "refund",')


def test_valid_object_is_normalised():
    assert validate_triage(extract_json(GOOD)) == (CLEAN, [])
    clean, errors = validate_triage({**CLEAN, "category": "Refund", "currency": "eur", "amount": None})
    assert errors == [] and clean["category"] == "refund" and clean["currency"] == "EUR" and clean["amount"] is None


def test_every_problem_is_reported():
    bad = {"category": "complaint", "amount": -5, "currency": "JPY", "urgent": "yes", "extra": 1}
    clean, errors = validate_triage(bad)
    assert clean is None
    text = " | ".join(errors)
    for word in ("missing field: summary", "unexpected field: extra", "category", "amount", "currency", "urgent"):
        assert word in text
    assert len(errors) == 6


def test_types_are_strict():
    assert validate_triage({**CLEAN, "amount": True})[0] is None  # a bool is not an amount
    assert validate_triage({**CLEAN, "amount": "42.10"})[0] is None
    assert validate_triage({**CLEAN, "urgent": 1})[0] is None
    assert validate_triage({**CLEAN, "summary": "x" * 201})[0] is None
    assert validate_triage({**CLEAN, "summary": "x" * 200})[1] == []
    assert validate_triage(["refund"])[0] is None


def test_first_valid_reply_returns_without_repair():
    llm = ScriptedLLM(["```json\n" + GOOD + "\n```"])
    assert triage(llm, TICKET) == CLEAN
    assert len(llm.calls) == 1
    assert llm.calls[0].system == TRIAGE_INSTRUCTIONS
    assert llm.calls[0].messages == [{"role": "user", "content": TICKET}]


def test_repair_prompt_carries_reply_and_errors():
    first = '{"category": "Refund request", "amount": 42.10, "currency": "EUR", "urgent": false, "summary": "Double charge."}'
    llm = ScriptedLLM([first, GOOD])
    assert triage(llm, TICKET) == CLEAN
    retry = llm.calls[1].messages
    assert [m["role"] for m in retry] == ["user", "assistant", "user"]
    assert retry[1]["content"] == first
    assert "category" in retry[2]["content"] and "JSON" in retry[2]["content"]


def test_unparseable_reply_is_repaired_too():
    llm = ScriptedLLM(["Here is the triage: category refund, 42.10 EUR.", GOOD])
    assert triage(llm, TICKET) == CLEAN
    assert "not valid JSON" in llm.calls[1].messages[-1]["content"]


def test_gives_up_after_max_attempts():
    llm = ScriptedLLM(['{"category": "refund"}'] * 5)
    with pytest.raises(StructuredOutputError) as err:
        triage(llm, TICKET, max_attempts=3)
    assert len(llm.calls) == 3 and err.value.attempts == 3
    assert "missing field: summary" in err.value.errors


def test_truncated_reply_is_not_repaired():
    llm = ScriptedLLM([GOOD, GOOD])
    with pytest.raises(StructuredOutputError) as err:
        triage(llm, TICKET, max_tokens=8)
    assert len(llm.calls) == 1 and err.value.attempts == 1
