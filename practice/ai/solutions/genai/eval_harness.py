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
    text = " ".join(str(text).split()).casefold()
    return text[:-1] if text.endswith(".") else text


def grade_exact(output: str, expected: str) -> Grade:
    """Pass when the normalised output equals the normalised expected answer."""
    if normalise(output) == normalise(expected):
        return Grade(True, "exact match")
    return Grade(False, f"expected {expected!r}, got {output!r}")


def grade_regex(output: str, pattern: str) -> Grade:
    """Pass when ``pattern`` is found anywhere in the output (``re.search``, case-insensitive)."""
    if re.search(pattern, output, flags=re.IGNORECASE):
        return Grade(True, f"matched /{pattern}/")
    return Grade(False, f"no match for /{pattern}/")


def grade_json_field(output: str, field: str, expected: Any) -> Grade:
    """Parse the whole output as a JSON object and compare the value at a dotted ``field`` path with ``expected``.

    Fails (never raises) when the output is not JSON, not an object, or the field is missing.
    """
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return Grade(False, "not valid JSON")
    value: Any = data
    for part in field.split("."):
        if not isinstance(value, dict):
            return Grade(False, f"not a JSON object at {part!r}")
        if part not in value:
            return Grade(False, f"missing field {field!r}")
        value = value[part]
    if value == expected:
        return Grade(True, f"{field} == {expected!r}")
    return Grade(False, f"{field} is {value!r}, expected {expected!r}")


def grade(case: GoldenCase, output: str) -> Grade:
    """Dispatch to the case's grader."""
    if case.grader == "exact":
        return grade_exact(output, case.expected)
    if case.grader == "regex":
        return grade_regex(output, case.expected)
    if case.grader == "json_field":
        if not case.field:
            raise ValueError(f"case {case.id}: json_field grader needs a field")
        return grade_json_field(output, case.field, case.expected)
    raise ValueError(f"case {case.id}: unknown grader {case.grader!r}")


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
    results = []
    for case in cases:
        try:
            reply = client.create(
                messages=[{"role": "user", "content": build_prompt(case.input)}],
                system=system,
                max_tokens=max_tokens,
                temperature=0.0,
            )
        except LLMError as exc:
            results.append(
                {"id": case.id, "passed": False, "reason": f"error: {exc}", "output": None, "tags": case.tags, "error": True}
            )
            continue
        g = grade(case, reply.text)
        results.append({"id": case.id, "passed": g.passed, "reason": g.reason, "output": reply.text, "tags": case.tags, "error": False})
    return results


def wilson_interval(passed: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a pass rate (NIST/SEMATECH e-Handbook 7.2.4.1). z = 1.96 gives about 95%."""
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= passed <= n:
        raise ValueError("passed must be between 0 and n")
    p = passed / n
    z2 = z * z
    centre = p + z2 / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    denom = 1 + z2 / n
    return ((centre - margin) / denom, (centre + margin) / denom)


def summarise(results: list[dict], z: float = 1.96) -> dict:
    """Pass count, pass rate, Wilson interval, error count, and ``by_tag`` {tag: (passed, n)}."""
    n = len(results)
    passed = sum(r["passed"] for r in results)
    by_tag: dict[str, list[int]] = {}
    for r in results:
        for tag in r["tags"]:
            counts = by_tag.setdefault(tag, [0, 0])
            counts[0] += int(r["passed"])
            counts[1] += 1
    return {
        "n": n,
        "passed": passed,
        "pass_rate": passed / n,
        "ci": wilson_interval(passed, n, z),
        "errors": sum(r["error"] for r in results),
        "by_tag": {tag: (p, t) for tag, (p, t) in sorted(by_tag.items())},
    }


def mcnemar_exact_p(only_a: int, only_b: int) -> float:
    """Two-sided exact McNemar test: a binomial test of the discordant pairs against p = 0.5."""
    n = only_a + only_b
    if n == 0:
        return 1.0
    k = min(only_a, only_b)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def compare(results_a: list[dict], results_b: list[dict]) -> dict:
    """Pair two runs of the same cases by id.

    Returns ``both``, ``neither`` (counts), ``fixes`` (ids failing in A, passing in B), ``regressions`` (ids passing
    in A, failing in B) and ``p_value`` (exact McNemar). Raises ``ValueError`` if the runs cover different ids.
    """
    a = {r["id"]: r["passed"] for r in results_a}
    b = {r["id"]: r["passed"] for r in results_b}
    if a.keys() != b.keys() or len(a) != len(results_a) or len(b) != len(results_b):
        raise ValueError("both runs must cover the same, unique case ids")
    ids = [r["id"] for r in results_a]
    fixes = [i for i in ids if not a[i] and b[i]]
    regressions = [i for i in ids if a[i] and not b[i]]
    return {
        "both": sum(a[i] and b[i] for i in ids),
        "neither": sum(not a[i] and not b[i] for i in ids),
        "fixes": fixes,
        "regressions": regressions,
        "p_value": mcnemar_exact_p(len(regressions), len(fixes)),
    }
