import pytest
from production.iv_failure_triage import LABELS, EvalRecord, classify, next_step, triage

pytestmark = pytest.mark.exercise


def rec(qid, gold, retrieved, cited, correct):
    return EvalRecord(qid, frozenset(gold), tuple(retrieved), tuple(cited), correct)


def test_pass_when_correct_and_citations_were_in_prompt():
    assert classify(rec("q1", {"c7"}, ["c7", "c2"], ["c7"], True)) == "pass"


def test_pass_without_citations():
    assert classify(rec("q1", {"c7"}, ["c7"], [], True)) == "pass"


def test_citation_outside_prompt_is_flagged_even_when_correct():
    assert classify(rec("q2", {"c7"}, ["c2", "c3"], ["c7"], True)) == "unsupported_citation"


def test_citation_check_comes_before_retrieval_miss():
    assert classify(rec("q3", {"c7"}, ["c2"], ["c9"], False)) == "unsupported_citation"


def test_retrieval_miss_when_no_gold_chunk_retrieved():
    assert classify(rec("q4", {"c7", "c8"}, ["c1", "c2"], ["c1"], False)) == "retrieval_miss"


def test_generation_error_when_gold_was_in_prompt():
    assert classify(rec("q5", {"c7"}, ["c1", "c7"], ["c1"], False)) == "generation_error"


def test_one_gold_chunk_is_enough_to_rule_out_retrieval():
    assert classify(rec("q6", {"c7", "c8"}, ["c8"], [], False)) == "generation_error"


def test_missing_gold_is_an_error():
    with pytest.raises(ValueError):
        classify(rec("q7", set(), ["c1"], [], False))


RUN = [
    rec("q1", {"c7"}, ["c7"], ["c7"], True),
    rec("q2", {"c3"}, ["c1", "c2"], [], False),
    rec("q3", {"c4"}, ["c5", "c6"], ["c5"], False),
    rec("q4", {"c9"}, ["c9", "c1"], ["c1"], False),
    rec("q5", {"c2"}, ["c2"], ["c8"], True),
]


def test_triage_counts_every_label_in_order():
    counts = triage(RUN)
    assert list(counts) == list(LABELS)
    assert counts == {"pass": 1, "unsupported_citation": 1, "retrieval_miss": 2, "generation_error": 1}


def test_triage_of_nothing():
    assert triage([]) == {label: 0 for label in LABELS}


def test_next_step_targets_the_largest_bucket():
    assert next_step(triage(RUN)).startswith("Fix retrieval first")


def test_next_step_tie_prefers_retrieval_over_generation():
    counts = {"pass": 5, "unsupported_citation": 0, "retrieval_miss": 2, "generation_error": 2}
    assert next_step(counts).startswith("Fix retrieval first")


def test_next_step_tie_prefers_citations_over_retrieval():
    counts = {"pass": 5, "unsupported_citation": 1, "retrieval_miss": 1, "generation_error": 0}
    assert next_step(counts).startswith("Make citations checkable")


def test_next_step_with_no_failures():
    assert next_step({"pass": 3}).startswith("No failures")
