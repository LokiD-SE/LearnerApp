"""Getting JSON out of an LLM you can trust: extract, validate, and repair-and-retry.

Running example: SandPay (a fictional payments company) triages support tickets with an LLM. The model must
answer with one JSON object:

    {"category": "refund" | "chargeback" | "fraud" | "other",
     "amount": number >= 0 or null, "currency": "EUR" | "GBP" | "USD" or null,
     "urgent": true | false, "summary": string of at most 200 characters}

No pydantic or jsonschema here - plain dict checks, so every rule is visible. The model client is injected
(``llm`` with ``create(system=..., messages=..., max_tokens=...)``), so tests pass a ``ScriptedLLM``.
"""

from __future__ import annotations

import json
import re
from typing import Any

CATEGORIES = ("refund", "chargeback", "fraud", "other")
CURRENCIES = ("EUR", "GBP", "USD")
FIELDS = ("category", "amount", "currency", "urgent", "summary")
MAX_SUMMARY = 200

TRIAGE_INSTRUCTIONS = (
    "You triage SandPay support tickets. Reply with ONLY a JSON object, no prose and no code fences, with exactly "
    "these keys: category (one of refund, chargeback, fraud, other), amount (number >= 0, or null if no amount "
    "is given), currency (EUR, GBP or USD, or null), urgent (true or false), summary (at most 200 characters)."
)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class StructuredOutputError(Exception):
    """No valid object after the allowed attempts, or the reply was cut off. ``errors`` lists the last problems."""

    def __init__(self, message: str, errors: list[str], attempts: int):
        super().__init__(message)
        self.errors = errors
        self.attempts = attempts


def extract_json(text: str) -> Any:
    """Parse the JSON object in a model reply.

    Accepts bare JSON, JSON inside a Markdown code fence, or JSON with prose around it (takes the text from the
    first ``{`` to the last ``}``). Raises ``ValueError`` (``json.JSONDecodeError`` is one) if nothing parses.
    """
    text = text.strip()
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    elif not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end < start:
            raise ValueError("no JSON object in the reply")
        text = text[start : end + 1]
    return json.loads(text)


def _is_number(value: Any) -> bool:
    # bool is a subclass of int in Python, but true/false is not an amount.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_triage(obj: Any) -> tuple[dict | None, list[str]]:
    """Check ``obj`` against the triage contract. Returns ``(clean, [])`` or ``(None, errors)``.

    ``clean`` is a normalised copy: category lower-case and currency upper-case (enum values are compared
    case-insensitively), amount as a float. Every problem is reported, not just the first.
    """
    if not isinstance(obj, dict):
        return None, [f"expected a JSON object, got {type(obj).__name__}"]
    errors = [f"missing field: {name}" for name in FIELDS if name not in obj]
    errors += [f"unexpected field: {name}" for name in obj if name not in FIELDS]
    clean: dict[str, Any] = {}

    category = obj.get("category")
    if "category" in obj:
        if isinstance(category, str) and category.lower() in CATEGORIES:
            clean["category"] = category.lower()
        else:
            errors.append(f"category must be one of {', '.join(CATEGORIES)}, got {category!r}")

    amount = obj.get("amount")
    if "amount" in obj:
        if amount is None:
            clean["amount"] = None
        elif not _is_number(amount):
            errors.append(f"amount must be a number or null, got {amount!r}")
        elif amount < 0:
            errors.append(f"amount must be >= 0, got {amount!r}")
        else:
            clean["amount"] = float(amount)

    currency = obj.get("currency")
    if "currency" in obj:
        if currency is None:
            clean["currency"] = None
        elif isinstance(currency, str) and currency.upper() in CURRENCIES:
            clean["currency"] = currency.upper()
        else:
            errors.append(f"currency must be one of {', '.join(CURRENCIES)} or null, got {currency!r}")

    if "urgent" in obj:
        if isinstance(obj["urgent"], bool):
            clean["urgent"] = obj["urgent"]
        else:
            errors.append(f"urgent must be true or false, got {obj['urgent']!r}")

    if "summary" in obj:
        summary = obj["summary"]
        if not isinstance(summary, str):
            errors.append(f"summary must be a string, got {summary!r}")
        elif len(summary) > MAX_SUMMARY:
            errors.append(f"summary must be at most {MAX_SUMMARY} characters, got {len(summary)}")
        else:
            clean["summary"] = summary

    return (None, errors) if errors else (clean, [])


def triage(llm: Any, ticket: str, max_attempts: int = 3, max_tokens: int = 300) -> dict:
    """Ask the model to triage ``ticket``; parse and validate; repair-and-retry on invalid output.

    - Each attempt calls ``llm.create(system=TRIAGE_INSTRUCTIONS, messages=..., max_tokens=max_tokens)``.
    - ``stop_reason == "max_tokens"`` means the JSON is cut off: raise ``StructuredOutputError`` at once - a
      repair prompt cannot fix a limit that is too low.
    - Otherwise, if the reply does not parse or validate, append the model's reply as an ``assistant`` message
      and a ``user`` message that lists the errors and asks for only the corrected JSON, then try again.
    - After ``max_attempts`` failed attempts, raise ``StructuredOutputError`` with the last errors.
    """
    messages: list[dict[str, Any]] = [{"role": "user", "content": ticket}]
    errors: list[str] = []
    for attempt in range(1, max_attempts + 1):
        reply = llm.create(system=TRIAGE_INSTRUCTIONS, messages=messages, max_tokens=max_tokens)
        if reply.stop_reason == "max_tokens":
            raise StructuredOutputError("reply truncated at max_tokens", ["reply truncated"], attempt)
        try:
            obj = extract_json(reply.text)
        except ValueError as error:
            errors = [f"not valid JSON: {error}"]
        else:
            clean, errors = validate_triage(obj)
            if clean is not None:
                return clean
        messages.append({"role": "assistant", "content": reply.text})
        messages.append(
            {
                "role": "user",
                "content": "Your reply was not valid:\n- "
                + "\n- ".join(errors)
                + "\nReply with only the corrected JSON object.",
            }
        )
    raise StructuredOutputError(f"no valid triage after {max_attempts} attempts", errors, max_attempts)
