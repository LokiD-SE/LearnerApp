"""Checks exercises/genai/prompt_output_parsing.py - lesson prompt-engineering."""

import pytest
from genai.prompt_output_parsing import (
    REMINDER,
    SYSTEM,
    Answer,
    NoAnswer,
    TruncatedReply,
    ask_with_reasoning,
    extract,
)
from llm_fake import ScriptedLLM

pytestmark = pytest.mark.exercise

Q = "A merchant sells 200.00 EUR. SandPay charges 1.4% plus 0.25 EUR per payment. What is the fee?"
GOOD = "<reasoning>1.4% of 200.00 is 2.80. 2.80 + 0.25 = 3.05.</reasoning>\n<answer>3.05</answer>"
LONG = "<reasoning>" + " ".join(["First, the percentage part."] * 20) + "</reasoning><answer>3.05</answer>"


def reply_of(text, max_tokens=256):
    return ScriptedLLM([text]).create(messages=[{"role": "user", "content": "q"}], max_tokens=max_tokens)


class TestExtract:
    def test_answer_and_reasoning(self):
        assert extract(reply_of(GOOD)) == ("3.05", "1.4% of 200.00 is 2.80. 2.80 + 0.25 = 3.05.")

    def test_last_answer_wins_and_text_is_stripped(self):
        text = "<answer>2.80</answer> wait, add the fixed fee <answer> 3.05 </answer>"
        assert extract(reply_of(text)) == ("3.05", "")

    @pytest.mark.parametrize("text", ["The fee is 3.05 EUR.", "<answer>  </answer>", "<answer>3.05"])
    def test_missing_or_empty_answer_is_none(self, text):
        assert extract(reply_of(text)) is None

    def test_truncated_reply_raises_even_if_it_has_an_answer_tag(self):
        reply = reply_of("<answer>3</answer>" + " more" * 40, max_tokens=10)
        assert reply.stop_reason == "max_tokens"
        with pytest.raises(TruncatedReply):
            extract(reply)

    def test_multiline_reasoning(self):
        text = "<reasoning>\nline one\nline two\n</reasoning>\n<answer>\n3.05\n</answer>"
        assert extract(reply_of(text)) == ("3.05", "line one\nline two")


class TestAskWithReasoning:
    def test_first_good_reply(self):
        llm = ScriptedLLM([GOOD])
        assert ask_with_reasoning(llm, Q) == Answer("3.05", "1.4% of 200.00 is 2.80. 2.80 + 0.25 = 3.05.", 1)
        call = llm.calls[0]
        assert call.system == SYSTEM and call.temperature == 0.0 and call.max_tokens == 200
        assert call.messages == [{"role": "user", "content": Q}]

    def test_truncation_retries_same_messages_with_double_budget(self):
        llm = ScriptedLLM([LONG, GOOD])
        result = ask_with_reasoning(llm, Q, max_tokens=60)
        assert result.attempts == 2 and result.answer == "3.05"
        assert [c.max_tokens for c in llm.calls] == [60, 120]
        assert llm.calls[1].messages == llm.calls[0].messages

    def test_missing_tags_appends_reply_and_reminder(self):
        llm = ScriptedLLM(["The fee is 3.05 EUR.", GOOD])
        result = ask_with_reasoning(llm, Q)
        assert result.attempts == 2
        assert llm.calls[1].messages == [
            {"role": "user", "content": Q},
            {"role": "assistant", "content": "The fee is 3.05 EUR."},
            {"role": "user", "content": REMINDER},
        ]
        assert llm.calls[1].max_tokens == 200

    def test_both_repairs_in_one_run(self):
        llm = ScriptedLLM([LONG, "The fee is 3.05 EUR.", GOOD])
        result = ask_with_reasoning(llm, Q, max_tokens=60)
        assert result.attempts == 3
        assert [c.max_tokens for c in llm.calls] == [60, 120, 120]
        assert [m["role"] for m in llm.calls[2].messages] == ["user", "assistant", "user"]

    def test_gives_up_after_max_attempts(self):
        llm = ScriptedLLM(["3.05"] * 5)
        with pytest.raises(NoAnswer):
            ask_with_reasoning(llm, Q, max_attempts=3)
        assert len(llm.calls) == 3

    def test_input_messages_are_not_mutated_between_calls(self):
        llm = ScriptedLLM(["no tags", "still none", GOOD])
        ask_with_reasoning(llm, Q)
        assert [len(c.messages) for c in llm.calls] == [1, 3, 5]
