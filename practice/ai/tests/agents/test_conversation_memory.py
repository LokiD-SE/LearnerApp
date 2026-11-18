"""Checks exercises/agents/conversation_memory.py - lesson agent-memory-and-context."""

import pytest
from agents.conversation_memory import (
    CLEARED,
    SUMMARY_SYSTEM,
    ConversationMemory,
    SummaryTruncatedError,
    clear_old_tool_results,
    message_tokens,
    truncate_tool_result,
)
from llm_fake import OverloadedError, ScriptedLLM, count_tokens

pytestmark = pytest.mark.exercise

# A synthetic payout log (SandPay is fictional): 40 lines of 20 toy tokens each.
LOG = "\n".join(f"2026-11-14T09:{i:02d}:00Z payout po_{1000 + i} status=paid amount=12.50 EUR" for i in range(40))
SYSTEM = "You are SandPay's merchant support assistant."


def tool_pair(n, name, output):
    return [
        {"role": "assistant", "content": [{"type": "tool_use", "id": f"call_{n}", "name": name, "input": {"m": "m-204"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"call_{n}", "content": output}]},
    ]


def results(messages):
    return [b["content"] for m in messages if isinstance(m["content"], list) for b in m["content"] if b["type"] == "tool_result"]


class TestTruncateToolResult:
    def test_fixture_sizes(self):
        assert count_tokens(LOG) == 800
        assert count_tokens("[... 0 lines omitted ...]") == 11

    def test_short_text_unchanged(self):
        assert truncate_tool_result("status=paid", 5) == "status=paid"
        assert truncate_tool_result(LOG, 800) == LOG

    def test_keeps_head_and_tail_with_marker(self):
        lines = LOG.splitlines()
        out = truncate_tool_result(LOG, 60)
        assert out.splitlines() == [lines[0], "[... 38 lines omitted ...]", lines[-1]]
        assert count_tokens(out) == 51

    def test_tail_uses_what_the_head_left(self):
        lines = LOG.splitlines()
        # budget 100 - 11 = 89: head gets 2 lines (40 <= 44), tail then fits 2 more (80 <= 89)
        out = truncate_tool_result(LOG, 100)
        assert out.splitlines() == lines[:2] + ["[... 36 lines omitted ...]"] + lines[-2:]
        assert count_tokens(out) <= 100

    def test_never_exceeds_the_limit(self):
        for limit in (11, 25, 31, 47, 333):
            assert count_tokens(truncate_tool_result(LOG, limit)) <= limit

    def test_marker_only_when_no_line_fits(self):
        assert truncate_tool_result(LOG, 20) == "[... 40 lines omitted ...]"

    def test_limit_below_marker_raises(self):
        with pytest.raises(ValueError):
            truncate_tool_result(LOG, 10)


class TestClearOldToolResults:
    def build(self):
        msgs = [{"role": "user", "content": "Why is payout po_1039 late?"}]
        msgs += tool_pair(1, "get_payouts", "old payouts")
        msgs += tool_pair(2, "search_docs", "Payouts run daily at 06:00 UTC.")
        msgs += tool_pair(3, "get_merchant", "merchant m-204 active")
        msgs += tool_pair(4, "get_payouts", "new payouts")
        return msgs

    def test_keeps_the_newest(self):
        new, cleared = clear_old_tool_results(self.build(), keep=2)
        assert results(new) == [CLEARED, CLEARED, "merchant m-204 active", "new payouts"]
        assert cleared == 2

    def test_excluded_tools_never_cleared_and_not_counted(self):
        new, cleared = clear_old_tool_results(self.build(), keep=1, exclude_tools=("search_docs",))
        assert results(new) == [CLEARED, "Payouts run daily at 06:00 UTC.", CLEARED, "new payouts"]
        assert cleared == 2

    def test_tool_calls_stay(self):
        new, _ = clear_old_tool_results(self.build(), keep=0)
        calls = [b["name"] for m in new if isinstance(m["content"], list) for b in m["content"] if b["type"] == "tool_use"]
        assert calls == ["get_payouts", "search_docs", "get_merchant", "get_payouts"]
        assert results(new) == [CLEARED] * 4

    def test_frees_tokens(self):
        msgs = [{"role": "user", "content": "check"}] + tool_pair(1, "get_payouts", LOG) + tool_pair(2, "get_payouts", LOG)
        new, _ = clear_old_tool_results(msgs, keep=1)
        before = sum(message_tokens(m) for m in msgs)
        after = sum(message_tokens(m) for m in new)
        assert before - after == 800 - count_tokens(CLEARED)

    def test_already_cleared_not_counted_again(self):
        once, first = clear_old_tool_results(self.build(), keep=2)
        twice, second = clear_old_tool_results(once, keep=2)
        assert (first, second) == (2, 0)
        assert results(twice) == results(once)

    def test_does_not_modify_the_input(self):
        msgs = self.build()
        snapshot = repr(msgs)
        clear_old_tool_results(msgs, keep=0)
        assert repr(msgs) == snapshot

    def test_keep_larger_than_count(self):
        new, cleared = clear_old_tool_results(self.build(), keep=10)
        assert cleared == 0
        assert CLEARED not in results(new)


def conversation(llm, **kw):
    mem = ConversationMemory(llm, SYSTEM, **kw)
    mem.add({"role": "user", "content": "Refund 4821 for 12.50 EUR has not arrived."})  # 11 toy tokens
    mem.add({"role": "assistant", "content": "It was approved on Monday."})  # 6
    mem.add({"role": "user", "content": "I am merchant m-204, order 5531."})  # 10
    mem.add({"role": "assistant", "content": "Refunds arrive within 5 business days."})  # 7
    return mem


class TestCompact:
    def test_under_budget_does_nothing(self):
        llm = ScriptedLLM([])
        mem = conversation(llm, trigger_tokens=34, keep_recent=2)
        assert mem.history_tokens() == 34
        assert mem.compact() is False
        assert llm.calls == [] and mem.summary == "" and len(mem.messages) == 4

    def test_folds_old_turns_into_summary(self):
        llm = ScriptedLLM(["  Refund 4821 (12.50 EUR) approved Monday.  "])
        mem = conversation(llm, trigger_tokens=30, keep_recent=2, summary_max_tokens=40)
        assert mem.compact() is True
        assert mem.summary == "Refund 4821 (12.50 EUR) approved Monday."
        assert [m["content"] for m in mem.messages] == ["I am merchant m-204, order 5531.", "Refunds arrive within 5 business days."]
        assert mem.compactions == 1
        call = llm.calls[0]
        assert call.system == SUMMARY_SYSTEM and call.max_tokens == 40 and len(call.messages) == 1
        prompt = call.messages[0]["content"]
        assert "Previous summary:\n(none)" in prompt
        assert "user: Refund 4821 for 12.50 EUR has not arrived." in prompt
        assert "assistant: It was approved on Monday." in prompt
        assert "order 5531" not in prompt  # kept turns are not summarised

    def test_previous_summary_is_extended(self):
        llm = ScriptedLLM(["S1", "S2"])
        mem = conversation(llm, trigger_tokens=10, keep_recent=2)
        mem.compact()
        mem.add({"role": "user", "content": "Also payout po_1039 is late."})
        mem.add({"role": "assistant", "content": "Checking now."})
        assert mem.compact() is True
        assert "Previous summary:\nS1" in llm.calls[1].messages[0]["content"]
        assert mem.summary == "S2" and mem.compactions == 2

    def test_cut_moves_back_to_a_plain_user_turn(self):
        llm = ScriptedLLM(["summary"])
        mem = ConversationMemory(llm, SYSTEM, trigger_tokens=5, keep_recent=2)
        mem.add({"role": "user", "content": "Why is payout po_1039 late?"})
        for m in tool_pair(1, "get_payouts", "po_1039 scheduled"):
            mem.add(m)
        mem.add({"role": "assistant", "content": "It is scheduled for tomorrow."})
        mem.add({"role": "user", "content": "Thanks."})
        # cut at 3 would start with an assistant turn, 2 with a tool result, 1 with a tool call: back to 0 -> no compaction
        assert mem.compact() is False
        mem.add({"role": "assistant", "content": "You are welcome."})
        assert mem.compact() is True  # cut 4 -> 4 is "Thanks." (plain user)
        assert mem.messages[0]["content"] == "Thanks."
        assert "tool result: po_1039 scheduled" in llm.calls[0].messages[0]["content"]

    def test_truncated_summary_changes_nothing(self):
        llm = ScriptedLLM(["one two three four five six seven"])
        mem = conversation(llm, trigger_tokens=10, keep_recent=2, summary_max_tokens=3)
        before = [dict(m) for m in mem.messages]
        with pytest.raises(SummaryTruncatedError):
            mem.compact()
        assert mem.messages == before and mem.summary == "" and mem.compactions == 0

    def test_client_error_changes_nothing(self):
        mem = conversation(ScriptedLLM([OverloadedError("busy")]), trigger_tokens=10, keep_recent=2)
        with pytest.raises(OverloadedError):
            mem.compact()
        assert len(mem.messages) == 4 and mem.summary == ""


class TestRequestAndChat:
    def test_request_without_summary(self):
        mem = conversation(ScriptedLLM([]), trigger_tokens=100)
        req = mem.request()
        assert req["system"] == SYSTEM
        assert req["messages"] == mem.messages
        req["messages"][0]["content"] = "changed"
        assert mem.messages[0]["content"] != "changed"

    def test_request_with_summary(self):
        mem = conversation(ScriptedLLM([]), trigger_tokens=100)
        mem.summary = "Refund 4821 approved."
        assert mem.request()["system"] == SYSTEM + "\n\n<conversation_summary>\nRefund 4821 approved.\n</conversation_summary>"

    def test_chat_compacts_then_answers(self):
        llm = ScriptedLLM(["Refund 4821 approved Monday; merchant m-204.", "Payout po_1039 runs tomorrow."])
        mem = conversation(llm, trigger_tokens=39, keep_recent=2)
        assert mem.chat("Why is payout po_1039 late?") == "Payout po_1039 runs tomorrow."
        assert mem.compactions == 1
        answer_call = llm.calls[1]
        assert "<conversation_summary>\nRefund 4821 approved Monday; merchant m-204.\n</conversation_summary>" in answer_call.system
        assert answer_call.messages[-1] == {"role": "user", "content": "Why is payout po_1039 late?"}
        assert mem.messages[-1] == {"role": "assistant", "content": "Payout po_1039 runs tomorrow."}

    def test_chat_without_compaction_sends_everything(self):
        llm = ScriptedLLM(["ok"])
        mem = conversation(llm, trigger_tokens=1000)
        mem.chat("Thanks.", max_tokens=20)
        assert len(llm.calls) == 1 and llm.calls[0].max_tokens == 20
        assert len(llm.calls[0].messages) == 5 and llm.calls[0].system == SYSTEM
