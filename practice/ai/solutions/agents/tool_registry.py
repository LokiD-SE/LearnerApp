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
    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None:
        options = expected if isinstance(expected, list) else [expected]
        if not any(_TYPES[t](value) for t in options):
            errors.append(f"{path}: expected {' or '.join(options)}, got {_json_type(value)}")
            return errors  # the other checks assume the right type
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: must be one of {schema['enum']}, got {value!r}")
    if _TYPES["number"](value):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: must be >= {schema['minimum']}, got {value}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: must be <= {schema['maximum']}, got {value}")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: must be at least {schema['minLength']} characters")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: must be at most {schema['maxLength']} characters")
        # JSON Schema patterns are not implicitly anchored: search, not fullmatch. Anchor in the schema.
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: must match {schema['pattern']}")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            errors.extend(validate_input(schema["items"], item, f"{path}[{i}]"))
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{path}: missing required field '{name}'")
        if schema.get("additionalProperties") is False:
            for name in value:
                if name not in properties:
                    errors.append(f"{path}: unexpected field '{name}'")
        for name, sub in properties.items():
            if name in value:
                errors.extend(validate_input(sub, value[name], f"{path}.{name}"))
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
        problems = []
        if not NAME_PATTERN.match(name):
            problems.append(f"name {name!r} must match {NAME_PATTERN.pattern}")
        if name in self._tools:
            problems.append(f"tool {name!r} is already registered")
        if len(description.split()) < MIN_DESCRIPTION_WORDS:
            problems.append(f"description of {name!r} needs at least {MIN_DESCRIPTION_WORDS} words")
        if input_schema.get("type") != "object" or not isinstance(input_schema.get("properties"), dict):
            problems.append("input_schema must be an object schema with a 'properties' dict")
        else:
            properties = input_schema["properties"]
            for req in input_schema.get("required", []):
                if req not in properties:
                    problems.append(f"required field {req!r} is not in properties")
            for prop, sub in properties.items():
                if "description" not in sub:
                    problems.append(f"property {prop!r} has no description")
        if problems:
            raise ToolDefinitionError("; ".join(problems))
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
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in self._tools.values()
            if allowed is None or t.name in allowed
        ]


def to_openai_tool(definition: dict[str, Any], strict: bool = False) -> dict[str, Any]:
    """Convert a neutral definition to an OpenAI Responses API function tool.

    Shape (OpenAI function calling guide, read 14 November 2026): ``{"type": "function", "name",
    "description", "parameters", "strict"}``. Strict mode requires ``additionalProperties: false`` on every
    object and every property listed in ``required``; raise ``ToolDefinitionError`` if the schema does not.
    """
    schema = definition["input_schema"]
    if strict:
        problems = _strict_problems(schema, "input_schema")
        if problems:
            raise ToolDefinitionError("; ".join(problems))
    return {
        "type": "function",
        "name": definition["name"],
        "description": definition["description"],
        "parameters": schema,
        "strict": strict,
    }


def _strict_problems(schema: dict[str, Any], path: str) -> list[str]:
    problems = []
    if schema.get("type") == "object" or "properties" in schema:
        if schema.get("additionalProperties") is not False:
            problems.append(f"{path}: additionalProperties must be false")
        properties = schema.get("properties", {})
        missing = [p for p in properties if p not in schema.get("required", [])]
        if missing:
            problems.append(f"{path}: every property must be required (missing {missing})")
        for name, sub in properties.items():
            problems.extend(_strict_problems(sub, f"{path}.{name}"))
    if "items" in schema:
        problems.extend(_strict_problems(schema["items"], f"{path}[]"))
    return problems


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
    if mode not in ("auto", "required", "tool", "none"):
        raise ValueError(f"unknown mode {mode!r}")
    if (mode == "tool") != (tool is not None):
        raise ValueError("pass tool= exactly when mode is 'tool'")
    if provider == "anthropic":
        choice: dict[str, Any] = {"type": {"required": "any"}.get(mode, mode)}
        if tool is not None:
            choice["name"] = tool
        if not parallel and mode != "none":
            choice["disable_parallel_tool_use"] = True
        return {"tool_choice": choice}
    if provider == "openai":
        params: dict[str, Any] = {"tool_choice": {"type": "function", "name": tool} if mode == "tool" else mode}
        if not parallel:
            params["parallel_tool_calls"] = False
        return params
    raise ValueError(f"unknown provider {provider!r}")
