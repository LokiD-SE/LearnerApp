import pytest
from llm_fake import ScriptedLLM
from prod_cap_fixture import POLICIES
from production.cap_knowledge import (
    REFUSAL,
    SYSTEM_PROMPT,
    Chunk,
    Hit,
    KnowledgeBase,
    answer_question,
    build_prompt,
    check_citations,
    chunk_policy,
    slugify,
)

pytestmark = pytest.mark.exercise


def all_chunks():
    return [c for doc_id, text in POLICIES.items() for c in chunk_policy(doc_id, text)]


# --- chunking ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "heading, slug",
    [("Time limit", "time-limit"), ("Responding to a dispute", "responding-to-a-dispute"), ("  Fees & limits (EU)! ", "fees-limits-eu")],
)
def test_slugify(heading, slug):
    assert slugify(heading) == slug


def test_one_chunk_per_section_with_title_and_id():
    chunks = all_chunks()
    assert len(chunks) == 8
    assert [c.id for c in chunks[:4]] == ["refunds#time-limit", "refunds#partial-refunds", "refunds#refund-fees", "refunds#uncaptured-payments"]
    first = chunks[0]
    assert first.title == "Refunds - Time limit"
    assert first.text.startswith("A merchant can refund a captured payment within 180 days of the capture date. After")


def test_whitespace_is_collapsed_and_newlines_removed():
    for chunk in all_chunks():
        assert "\n" not in chunk.text and "  " not in chunk.text and chunk.text == chunk.text.strip()


def test_empty_sections_and_preamble_are_skipped():
    doc = "Intro text before any section.\n# Fees\nMore intro.\n## Empty\n\n## Card fees\nCards cost 1.4%.\n"
    assert chunk_policy("fees", doc) == [Chunk("fees#card-fees", "Fees - Card fees", "Cards cost 1.4%.")]


def test_doc_without_title_uses_the_doc_id():
    assert chunk_policy("misc", "## Hours\nSupport answers on weekdays.")[0].title == "misc - Hours"


# --- retrieval --------------------------------------------------------------------------------------------------


def test_duplicate_chunk_ids_are_rejected():
    c = Chunk("a#b", "A - B", "text")
    with pytest.raises(ValueError):
        KnowledgeBase([c, c])


@pytest.mark.parametrize(
    "question, best",
    [
        ("Can I refund part of a payment twice?", "refunds#partial-refunds"),
        ("Do I get the processing fee back when I refund?", "refunds#refund-fees"),
        ("How much is the dispute fee?", "disputes#dispute-fee"),
        ("Can I refund an authorised payment that was never captured?", "refunds#uncaptured-payments"),
    ],
)
def test_best_hit(question, best):
    assert KnowledgeBase(all_chunks()).search(question)[0].chunk.id == best


def test_scores_are_rounded_sorted_and_cut_at_k():
    hits = KnowledgeBase(all_chunks()).search("Can I refund part of a payment twice?")
    assert [(h.chunk.id, h.score) for h in hits] == [
        ("refunds#partial-refunds", 0.435),
        ("refunds#refund-fees", 0.244),
        ("refunds#time-limit", 0.208),
    ]
    assert len(KnowledgeBase(all_chunks()).search("Can I refund part of a payment twice?", k=1)) == 1


def test_min_score_filters_weak_hits():
    hits = KnowledgeBase(all_chunks()).search("When will my payout arrive?")
    assert [h.chunk.id for h in hits] == ["payouts#payout-schedule"]
    assert KnowledgeBase(all_chunks()).search("When will my payout arrive?", min_score=0.5) == []


def test_ties_are_broken_by_chunk_id():
    twins = [Chunk("b#x", "Same", "same words here"), Chunk("a#x", "Same", "same words here")]
    assert [h.chunk.id for h in KnowledgeBase(twins).search("same words here")] == ["a#x", "b#x"]


def test_empty_knowledge_base_and_k_zero():
    assert KnowledgeBase([]).search("anything") == []
    assert KnowledgeBase(all_chunks()).search("refund", k=0) == []


# --- prompt and citations ---------------------------------------------------------------------------------------


def test_build_prompt():
    hits = [Hit(Chunk("refunds#time-limit", "Refunds - Time limit", "Within 180 days."), 0.3), Hit(Chunk("disputes#dispute-fee", "Disputes - Dispute fee", "15.00 EUR."), 0.2)]
    assert build_prompt("How long?", hits) == (
        "[1] Refunds - Time limit (refunds#time-limit): Within 180 days.\n"
        "[2] Disputes - Dispute fee (disputes#dispute-fee): 15.00 EUR.\n"
        "\n"
        "Question: How long?"
    )


@pytest.mark.parametrize(
    "text",
    [
        "You can refund within 180 days [1].",
        "You can refund within 180 days. [1] After that the button is disabled [1].",
        "Partial refunds are allowed [3]! The total is capped [2][3].",
        REFUSAL,
    ],
)
def test_well_cited_answers_have_no_problems(text):
    assert check_citations(text, 3) == []


def test_citation_problems():
    text = "You can refund within 180 days [1]. SandPay keeps the fee [4]. Contact us."
    assert check_citations(text, 3) == ["sentence 2 cites [4], but there are only 3 sources", "sentence 3 has no citation"]
    assert check_citations("Refunds are free [0].", 2) == ["sentence 1 cites [0], but there are only 2 sources"]


# --- answering --------------------------------------------------------------------------------------------------


def test_answered_with_one_model_call():
    llm = ScriptedLLM(["You can refund a captured payment within 180 days of the capture date [1]."])
    answer = answer_question(llm, KnowledgeBase(all_chunks()), "How long do I have to refund a payment?")
    assert (answer.status, answer.sources, answer.problems) == ("answered", ["refunds#time-limit", "disputes#responding-to-a-dispute"], [])
    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call.system == SYSTEM_PROMPT
    assert call.messages == [{"role": "user", "content": build_prompt("How long do I have to refund a payment?", KnowledgeBase(all_chunks()).search("How long do I have to refund a payment?"))}]


def test_uncited_answer_is_rejected_but_kept():
    llm = ScriptedLLM(["You can refund within 180 days [1]. Refunds are always free."])
    answer = answer_question(llm, KnowledgeBase(all_chunks()), "How long do I have to refund a payment?")
    assert answer.status == "rejected"
    assert answer.problems == ["sentence 2 has no citation"]
    assert answer.text.startswith("You can refund")


def test_model_refusal():
    answer = answer_question(ScriptedLLM([REFUSAL]), KnowledgeBase(all_chunks()), "What is the capital of France?")
    assert (answer.status, answer.text) == ("refused", REFUSAL)
    assert answer.sources == ["refunds#time-limit", "refunds#refund-fees", "disputes#dispute-fee"]


def test_no_hits_refuses_without_calling_the_model():
    llm = ScriptedLLM([])
    answer = answer_question(llm, KnowledgeBase(all_chunks()), "zebra")
    assert (answer.status, answer.text, answer.sources) == ("refused", REFUSAL, [])
    assert llm.calls == []
