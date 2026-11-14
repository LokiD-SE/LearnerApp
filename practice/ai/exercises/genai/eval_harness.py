"""An offline evaluation harness for an LLM feature - lesson llm-evaluation-and-guardrails.

A golden set of ``GoldenCase`` s is run through the feature, each output is scored by a deterministic code grader
(exact match, regular expression or a JSON field), and the pass rate is reported with a Wilson score interval.
``compare`` pairs two runs case by case - fixes, regressions and an exact McNemar p-value - which is how you decide
whether prompt version B is really better than version A.

The client is passed in (dependency injection), so tests use the offline ``ScriptedLLM``.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Callable

from llm_fake import LLMError


@dataclass(frozen=True)
class GoldenCase:
    id: str
    input: str
    expected: Any
    grader: str = "exact"  # "exact" | "regex" | "json_field"
    field: str | None = None  # dotted path, for grader "json_field"
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Grade:
    passed: bool
    reason: str


def normalise(text: str) -> str:
    """Case-fold, collapse runs of whitespace to one space, strip, and drop one trailing full stop."""
    raise NotImplementedError


def grade_exact(output: str, expected: str) -> Grade:
    """Pass when the normalised output equals the normalised expected answer."""
    raise NotImplementedError


def grade_regex(output: str, pattern: str) -> Grade:
    """Pass when ``pattern`` is found anywhere in the output (``re.search``, case-insensitive)."""
    raise NotImplementedError


def grade_json_field(output: str, field: str, expected: Any) -> Grade:
    """Parse the whole output as a JSON object and compare the value at a dotted ``field`` path with ``expected``.

    Fails (never raises) when the output is not JSON, not an object, or the field is missing.
    """
    raise NotImplementedError


def grade(case: GoldenCase, output: str) -> Grade:
    """Dispatch to the case's grader."""
    raise NotImplementedError


def run_eval(
    client: Any,
    cases: list[GoldenCase],
    system: str,
    build_prompt: Callable[[str], str],
    max_tokens: int = 200,
) -> list[dict]:
    """Run every case once at temperature 0 and grade it.

    Returns one dict per case: ``id``, ``passed``, ``reason``, ``output``, ``tags``, ``error`` (bool). An API error
    on one case is recorded as a failed case with ``error=True`` and the run continues.
    """
    raise NotImplementedError


def wilson_interval(passed: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a pass rate (NIST/SEMATECH e-Handbook 7.2.4.1). z = 1.96 gives about 95%."""
    raise NotImplementedError


def summarise(results: list[dict], z: float = 1.96) -> dict:
    """Pass count, pass rate, Wilson interval, error count, and ``by_tag`` {tag: (passed, n)}."""
    raise NotImplementedError


def mcnemar_exact_p(only_a: int, only_b: int) -> float:
    """Two-sided exact McNemar test: a binomial test of the discordant pairs against p = 0.5."""
    raise NotImplementedError


def compare(results_a: list[dict], results_b: list[dict]) -> dict:
    """Pair two runs of the same cases by id.

    Returns ``both``, ``neither`` (counts), ``fixes`` (ids failing in A, passing in B), ``regressions`` (ids passing
    in A, failing in B) and ``p_value`` (exact McNemar). Raises ``ValueError`` if the runs cover different ids.
    """
    raise NotImplementedError
