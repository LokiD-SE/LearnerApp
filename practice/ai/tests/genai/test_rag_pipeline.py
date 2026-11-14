"""Checks exercises/genai/rag_pipeline.py - lesson retrieval-augmented-generation."""

import pytest
from genai.rag_pipeline import (
    REFUSAL,
    SYSTEM_PROMPT,
    Source,
    answer_question,
    build_prompt,
    check_citations,
    extract_citations,
)
from llm_fake import ScriptedLLM

pytestmark = pytest.mark.exercise

TIMING = Source("Refunds > How long refunds take", "The money usually reaches the customer within 5 to 10 business days.")
LIMITS = Source("Refunds > Refund limits", "You cannot refund a payment that is older than 180 days.")
FEES = Source("Fees > Card payment fees", "European cards cost 1.4% + 0.25 EUR per successful payment.")


def retriever(*pairs):
    calls = []

    def retrieve(question):
        calls.append(question)
        return list(pairs)

    retrieve.calls = calls
    return retrieve


class TestPrompt:
    def test_numbered_sources_then_question(self):
        assert build_prompt("How long?", [TIMING, LIMITS]) == (
            "<sources>\n"
            "[1] Refunds > How long refunds take\n"
            "The money usually reaches the customer within 5 to 10 business days.\n"
            "\n"
            "[2] Refunds > Refund limits\n"
            "You cannot refund a payment that is older than 180 days.\n"
            "</sources>\n"
            "\n"
            "Question: How long?"
        )

    def test_no_sources(self):
        assert build_prompt("Q?", []) == "<sources>\n</sources>\n\nQuestion: Q?"


class TestCitations:
    def test_extract(self):
        assert extract_citations("A [2]. B [1, 3]. C [2][10]. Not [x] or [ ].") == [2, 1, 3, 2, 10]

    def test_good_answers_and_refusal(self):
        assert check_citations("Refunds take 5 to 10 business days [1]. Older than 180 days fails [2].", 2) == []
        assert check_citations("Refunds take 5 to 10 business days. [1]", 1) == []
        assert check_citations(f"  {REFUSAL}\n", 0) == []

    def test_out_of_range_and_missing(self):
        assert check_citations("It takes 5 days [3].", 2) == ["cites [3]: no such source (2 given)"]
        assert check_citations("It takes [0] days [4] or [4].", 2) == [
            "cites [0]: no such source (2 given)",
            "cites [4]: no such source (2 given)",
        ]
        assert check_citations("It takes 5 days.", 2) == ["no citations"]

    def test_uncited_sentence(self):
        problems = check_citations("It takes 5 to 10 days [1]. Ask your bank to hurry! Fees apply [2].", 2)
        assert problems == ["uncited sentence: Ask your bank to hurry!"]


class TestAnswerQuestion:
    def test_answers_with_valid_citations_and_sends_the_context(self):
        llm = ScriptedLLM(["It usually takes 5 to 10 business days [1]."])
        retrieve = retriever((TIMING, 0.9), (LIMITS, 0.6), (FEES, 0.1))
        result = answer_question("How long does a refund take?", retrieve, llm, min_score=0.5)
        assert (result.status, result.text, result.cited) == ("answered", "It usually takes 5 to 10 business days [1].", [1])
        assert result.sources == [TIMING, LIMITS]  # FEES is below min_score
        assert retrieve.calls == ["How long does a refund take?"]
        (request,) = llm.calls
        assert request.system == SYSTEM_PROMPT and request.temperature == 0 and request.max_tokens == 300
        assert request.messages == [{"role": "user", "content": build_prompt("How long does a refund take?", [TIMING, LIMITS])}]

    def test_max_sources(self):
        llm = ScriptedLLM(["Yes [1]."])
        result = answer_question("Q?", retriever((TIMING, 0.9), (LIMITS, 0.8), (FEES, 0.7)), llm, max_sources=2)
        assert result.sources == [TIMING, LIMITS]

    def test_refuses_without_calling_the_model_when_nothing_is_relevant(self):
        llm = ScriptedLLM([])  # any call would fail: the script is empty
        result = answer_question("Do you take crypto?", retriever((FEES, 0.2)), llm, min_score=0.5)
        assert (result.status, result.text, result.sources) == ("refused", REFUSAL, [])
        assert llm.calls == []

    def test_model_refusal(self):
        llm = ScriptedLLM([REFUSAL])
        result = answer_question("Do you take crypto?", retriever((FEES, 0.7)), llm)
        assert (result.status, result.text) == ("refused", REFUSAL)

    @pytest.mark.parametrize(
        "reply, problem",
        [
            ("It takes 5 to 10 business days [4].", "cites [4]: no such source (1 given)"),
            ("It takes 5 to 10 business days.", "no citations"),
            ("It takes 5 to 10 days [1]. Banks may be faster.", "uncited sentence: Banks may be faster."),
        ],
    )
    def test_rejects_unsupported_answers(self, reply, problem):
        result = answer_question("How long?", retriever((TIMING, 0.9)), ScriptedLLM([reply]))
        assert result.status == "rejected" and result.text == REFUSAL and result.problems == [problem]
        assert result.sources == [TIMING]
