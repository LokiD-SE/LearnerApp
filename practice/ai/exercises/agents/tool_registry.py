"""Tool definitions an LLM can call: a registry, a small JSON Schema validator and provider request shapes.

Running example: SandPay (a fictional payments company) gives its support assistant a few functions -
look up a transaction, check a refund, convert a currency, issue a refund. Each tool is a *name*, a
*description* the model reads to decide when to call it, and a JSON Schema for its input.

The validator covers the subset of JSON Schema (draft 2020-12) that tool inputs usually need: ``type``
(including ``integer`` and lists of types), ``enum``, ``properties``, ``required``, ``additionalProperties: false``,
``minimum``/``maximum``, ``minLength``/``maxLength``, ``pattern`` and ``items``. Other keywords are ignored.
No jsonschema package - plain code, so every rule is visible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

# Anthropic documents tool names as matching ^[a-zA-Z0-9_-]{1,128}$ (Define tools, read 14 November 2026).
NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")
MIN_DESCRIPTION_WORDS = 12  # a house rule: one-line descriptions are the most common cause of wrong tool picks

_TYPES: dict[str, Callable[[Any], bool]] = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    # bool is a subclass of int in Python, but JSON true/false is not a number.
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    # JSON Schema: "integer" matches any number with a zero fractional part, so 5.0 is an integer.
    "integer": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and float(v).is_integer(),
}


class ToolDefinitionError(ValueError):
    """A tool definition breaks a rule (bad name, duplicate, thin description, malformed schema)."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    fn: Callable[..., Any]
    read_only: bool = True


def validate_input(schema: dict[str, Any], value: Any, path: str = "input") -> list[str]:
    """Return every way ``value`` breaks ``schema`` as ``"<path>: <problem>"`` strings (empty list = valid).

    Report all problems, not just the first, so one error message lets the model fix every field at once.
    """
    # Starting draft: only checks required fields. Types, enum, bounds, lengths, pattern, items and
    # additionalProperties are all ignored, and nested objects are never checked.
    errors = []
    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{path}: missing required field '{name}'")
    return errors


def _json_type(value: Any) -> str:
    for name in ("null", "boolean", "integer", "number", "string", "array", "object"):
        if _TYPES[name](value):
            return name
    return type(value).__name__


class ToolRegistry:
    """Holds the tools an application offers; hands the model only the definitions it is allowed to see."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        fn: Callable[..., Any],
        *,
        read_only: bool = True,
    ) -> Tool:
        """Check the definition and add it. Raises ``ToolDefinitionError`` listing what is wrong.

        Rules: the name matches ``NAME_PATTERN`` and is not taken; the description has at least
        ``MIN_DESCRIPTION_WORDS`` words; the schema is ``type: object`` with a ``properties`` dict; every
        ``required`` name is a property; every property has a ``description``.
        """
        # Starting draft: accepts anything - bad names, duplicates, one-line descriptions, broken schemas.
        tool = Tool(name, description, input_schema, fn, read_only)
        self._tools[name] = tool
        return tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        """Tool names in registration order."""
        return list(self._tools)

    def definitions(self, allowed: set[str] | frozenset[str] | None = None) -> list[dict[str, Any]]:
        """The ``tools`` request parameter in a neutral shape: ``{"name", "description", "input_schema"}``.

        Registration order (a stable order keeps a cached prompt prefix stable). With ``allowed``, only those
        tools are listed - a tool the model never sees is a tool it cannot be talked into calling.
        """
        # Starting draft: ignores ``allowed`` and offers every tool, including the ones that move money.
        return [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in self._tools.values()]


def to_openai_tool(definition: dict[str, Any], strict: bool = False) -> dict[str, Any]:
    """Convert a neutral definition to an OpenAI Responses API function tool.

    Shape (OpenAI function calling guide, read 14 November 2026): ``{"type": "function", "name",
    "description", "parameters", "strict"}``. Strict mode requires ``additionalProperties: false`` on every
    object and every property listed in ``required``; raise ``ToolDefinitionError`` if the schema does not.
    """
    raise NotImplementedError


def tool_choice_params(provider: str, mode: str = "auto", tool: str | None = None, parallel: bool = True) -> dict[str, Any]:
    """Request parameters for a tool choice, per provider.

    ``mode`` is ``"auto"`` (the model decides), ``"required"`` (must call some tool), ``"tool"`` (must call
    ``tool``) or ``"none"`` (must not call tools). ``parallel=False`` asks for at most one call per turn.

    - ``"anthropic"``: ``{"tool_choice": {"type": "auto" | "any" | "tool" (+ "name") | "none"}}``; parallel off
      is ``"disable_parallel_tool_use": true`` *inside* ``tool_choice`` (not for ``none``).
    - ``"openai"``: ``{"tool_choice": "auto" | "required" | "none" | {"type": "function", "name": ...}}``;
      parallel off is the top-level ``"parallel_tool_calls": false``.

    Raises ``ValueError`` for an unknown provider or mode, or a missing/extra ``tool``.
    """
    raise NotImplementedError
