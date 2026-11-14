"""Checks exercises/genai/context_budget.py - lesson how-llms-work."""

import pytest
from genai.context_budget import ask_within_window, fit_to_window
from llm_fake import ScriptedLLM, count_tokens

pytestmark = pytest.mark.exercise

SYSTEM = "You are SandPay's support assistant."  # 8 toy tokens
# A synthetic support chat (fictional). Toy token counts: 6, 6, 6, 5, 6.
CHAT = [
    {"role": "user", "content": "Refund 4821 has not arrived."},
    {"role": "assistant", "content": "It was approved on Monday."},
    {"role": "user", "content": "When will it reach me?"},
    {"role": "assistant", "content": "Usually within five days."},
    {"role": "user", "content": "Can you check payment 1932?"},
]


def size(messages):
    return count_tokens(SYSTEM) + sum(count_tokens(m["content"]) for m in messages)


class TestFitToWindow:
    def test_counts_are_what_the_tests_assume(self):
        assert count_tokens(SYSTEM) == 8
        assert [count_tokens(m["content"]) for m in CHAT] == [6, 6, 6, 5, 6]

    def test_everything_fits(self):
        kept, used = fit_to_window(SYSTEM, CHAT, context_window=100, max_output_tokens=50)
        assert kept == CHAT
        assert used == 37

    def test_the_reply_budget_counts_against_the_window(self):
        # 37 input tokens fit in 60 only if the reply gets at most 23
        assert fit_to_window(SYSTEM, CHAT, 60, 23)[0] == CHAT
        assert fit_to_window(SYSTEM, CHAT, 60, 24)[0] != CHAT

    def test_drops_oldest_first_and_starts_with_user(self):
        # dropping the first message alone would fit (8 + 23 + 20 = 51), but it leaves an assistant
        # message first, so that goes too
        kept, used = fit_to_window(SYSTEM, CHAT, context_window=51, max_output_tokens=20)
        assert kept == CHAT[2:]
        assert used == size(CHAT[2:]) == 25

    def test_keeps_as_much_as_fits(self):
        assert fit_to_window(SYSTEM, CHAT, context_window=57, max_output_tokens=20)[0] == CHAT
        assert fit_to_window(SYSTEM, CHAT, context_window=56, max_output_tokens=20)[0] == CHAT[2:]
        assert fit_to_window(SYSTEM, CHAT, context_window=45, max_output_tokens=20)[0] == CHAT[2:]
        assert fit_to_window(SYSTEM, CHAT, context_window=44, max_output_tokens=20)[0] == CHAT[4:]

    def test_newest_message_too_big_raises(self):
        with pytest.raises(ValueError):
            fit_to_window(SYSTEM, CHAT, context_window=33, max_output_tokens=20)

    def test_does_not_modify_the_input(self):
        before = [dict(m) for m in CHAT]
        fit_to_window(SYSTEM, CHAT, 40, 10)
        assert CHAT == before

    def test_uses_the_given_tokenizer(self):
        chars = len  # a "tokenizer" that counts characters
        kept, used = fit_to_window("sys", CHAT, context_window=3 + 27 + 10, max_output_tokens=10, count=chars)
        assert kept == CHAT[4:]
        assert used == 3 + len(CHAT[4]["content"])


class TestAskWithinWindow:
    def test_sends_only_what_fits(self):
        llm = ScriptedLLM(["Payment 1932 was declined: card expired."])
        result = ask_within_window(llm, SYSTEM, CHAT, context_window=50, max_output_tokens=20)
        assert len(llm.calls) == 1
        call = llm.calls[0]
        assert call.messages == CHAT[2:]
        assert call.system == SYSTEM
        assert call.max_tokens == 20
        assert result == {"text": "Payment 1932 was declined: card expired.", "dropped": 2, "truncated": False}

    def test_reports_a_cut_off_reply(self):
        llm = ScriptedLLM(["Payment 1932 was declined because the card on file expired last month."])
        result = ask_within_window(llm, SYSTEM, CHAT, context_window=100, max_output_tokens=5)
        assert result["truncated"] is True
        assert result["dropped"] == 0
        assert result["text"] == "Payment 1932 was declined because"
