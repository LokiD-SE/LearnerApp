"""Checks exercises/genai/approach_choice.py - lesson fine-tuning-vs-rag-vs-prompting."""

from dataclasses import replace

import pytest
from genai.approach_choice import Scenario, recommend, validate

pytestmark = pytest.mark.exercise

QUIET = Scenario(
    knowledge_change="never",
    needs_citations=False,
    gap="none",
    labelled_examples=100,
    latency_budget_ms=3000,
    requests_per_day=1000,
    prompt_tokens=800,
)


def test_no_gap_keeps_prompting():
    rec = recommend(QUIET)
    assert rec.scores == {"prompting": 3, "rag": 0, "fine_tuning": 0}
    assert rec.ranked == ["prompting", "rag", "fine_tuning"]
    assert rec.excluded == {} and len(rec.reasons) == 1


def test_fresh_facts_with_citations_lead_to_rag():
    s = replace(QUIET, knowledge_change="daily", needs_citations=True, gap="knowledge")
    rec = recommend(s)
    assert rec.scores == {"prompting": 1, "rag": 7, "fine_tuning": -2}
    assert rec.ranked[0] == "rag"
    assert len(rec.reasons) == 3


def test_monthly_change():
    rec = recommend(replace(QUIET, knowledge_change="monthly", gap="knowledge"))
    assert rec.scores == {"prompting": 1, "rag": 4, "fine_tuning": -1}


def test_style_gap_with_many_examples_tight_latency_and_volume_leads_to_fine_tuning():
    s = replace(
        QUIET, gap="style", labelled_examples=2000, latency_budget_ms=300, requests_per_day=200_000, prompt_tokens=1500
    )
    rec = recommend(s)
    assert rec.scores == {"prompting": 1, "rag": -1, "fine_tuning": 5}
    assert rec.ranked == ["fine_tuning", "prompting", "rag"]
    assert len(rec.reasons) == 4


def test_volume_threshold_is_inclusive():
    at = recommend(replace(QUIET, requests_per_day=50_000, prompt_tokens=1000))
    below = recommend(replace(QUIET, requests_per_day=49_999, prompt_tokens=1000))
    assert at.scores["fine_tuning"] == below.scores["fine_tuning"] + 1


def test_too_few_examples_excludes_fine_tuning():
    rec = recommend(replace(QUIET, gap="skill", labelled_examples=9))
    assert "fine_tuning" in rec.excluded
    assert "fine_tuning" not in rec.ranked
    assert rec.scores["fine_tuning"] == 2  # still scored, just not viable
    assert rec.ranked == ["prompting", "rag"]


@pytest.mark.parametrize("n, delta", [(10, -1), (49, -1), (50, 0), (499, 0), (500, 1)])
def test_example_count_bands(n, delta):
    rec = recommend(replace(QUIET, labelled_examples=n))
    assert rec.scores["fine_tuning"] == delta
    assert "fine_tuning" not in rec.excluded


def test_format_gap_ties_break_towards_the_simpler_approach():
    rec = recommend(replace(QUIET, gap="format", latency_budget_ms=499))
    # prompting 1+1 = 2, rag 0-1 = -1, fine_tuning 0+1+1 = 2: tie goes to prompting
    assert rec.scores == {"prompting": 2, "rag": -1, "fine_tuning": 2}
    assert rec.ranked == ["prompting", "fine_tuning", "rag"]


@pytest.mark.parametrize(
    "bad",
    [
        {"knowledge_change": "weekly"},
        {"gap": "tone"},
        {"labelled_examples": -1},
        {"latency_budget_ms": -5},
        {"requests_per_day": -1},
        {"prompt_tokens": -1},
    ],
)
def test_invalid_scenarios_are_rejected(bad):
    s = replace(QUIET, **bad)
    with pytest.raises(ValueError):
        validate(s)
    with pytest.raises(ValueError):
        recommend(s)
