"""A small prompt regression harness - lesson prompt-engineering.

Prompts are versioned like code: each ``PromptVersion`` has a name and a content hash, a fixed list of
``Case`` s is run against it, a deterministic grader scores each reply, and ``gate`` refuses a new version
that drops below the bar or breaks a case the old version passed.

Against the offline ``ScriptedLLM`` the "model" is whatever script the test supplies, so this harness tests
the *harness*; with a real model the same code measures the prompt.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class PromptVersion:
    name: str
    system: str
    user_template: str  # must contain {ticket}

    @property
    def fingerprint(self) -> str:
        """First 12 hex characters of sha256(system + NUL + user_template): changes whenever the text does."""
        raise NotImplementedError

    def render(self, ticket: str) -> dict:
        """Request kwargs for ``llm.create``: ``system``, one user message, ``max_tokens=20``, ``temperature=0.0``.

        The ticket is escaped (``&`` first, then ``<`` and ``>``) before it is put into ``{ticket}``.
        """
        raise NotImplementedError


@dataclass(frozen=True)
class Case:
    id: str
    ticket: str
    expected: str


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    expected: str
    got: str | None
    passed: bool


@dataclass
class SuiteResult:
    version: str
    fingerprint: str
    results: list[CaseResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        """Share of cases that passed, 0.0 for an empty suite."""
        raise NotImplementedError

    def passed_ids(self) -> set[str]:
        """Ids of the cases that passed."""
        raise NotImplementedError


def grade_label(reply_text: str, expected: str) -> tuple[str | None, bool]:
    """Deterministic grader: exactly one ``<label>x</label>`` and x equals ``expected``."""
    raise NotImplementedError


def run_suite(
    llm, version: PromptVersion, cases: list[Case], grader: Callable = grade_label
) -> SuiteResult:
    """Call the model once per case, in order, and grade every reply."""
    raise NotImplementedError


def compare(baseline: SuiteResult, candidate: SuiteResult) -> dict[str, list[str]]:
    """Case ids that broke (passed before, fail now) and that got fixed, each sorted."""
    raise NotImplementedError


def gate(baseline: SuiteResult, candidate: SuiteResult, min_pass_rate: float) -> tuple[bool, list[str]]:
    """Accept the candidate only if it meets ``min_pass_rate`` and breaks no case the baseline passed."""
    raise NotImplementedError
