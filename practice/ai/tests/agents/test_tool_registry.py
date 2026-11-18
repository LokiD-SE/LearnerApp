import pytest
from agents.tool_registry import (
    ToolDefinitionError,
    ToolRegistry,
    to_openai_tool,
    tool_choice_params,
    validate_input,
)

pytestmark = pytest.mark.exercise

TX_SCHEMA = {
    "type": "object",
    "properties": {
        "transaction_id": {"type": "string", "pattern": "^tx_[0-9]+$", "description": "SandPay transaction id, e.g. tx_1042."}
    },
    "required": ["transaction_id"],
    "additionalProperties": False,
}
FX_SCHEMA = {
    "type": "object",
    "properties": {
        "amount": {"type": "number", "minimum": 0, "description": "Amount in the source currency."},
        "from_currency": {"type": "string", "enum": ["EUR", "GBP", "USD"], "description": "Source currency."},
        "to_currency": {"type": "string", "enum": ["EUR", "GBP", "USD"], "description": "Target currency."},
    },
    "required": ["amount", "from_currency", "to_currency"],
    "additionalProperties": False,
}
DESC = "Look up one SandPay card transaction by its id and return its amount, currency, merchant and status."


def make_registry():
    reg = ToolRegistry()
    reg.register("get_transaction", DESC, TX_SCHEMA, lambda transaction_id: {"id": transaction_id})
    reg.register("convert_currency", "Convert an amount between EUR, GBP and USD at the daily reference rate of SandPay.", FX_SCHEMA, lambda **kw: kw)
    reg.register("issue_refund", "Issue a refund for a settled transaction; this moves money and cannot be undone.", TX_SCHEMA, lambda **kw: kw, read_only=False)
    return reg


def test_valid_input_has_no_errors():
    assert validate_input(TX_SCHEMA, {"transaction_id": "tx_1042"}) == []
    assert validate_input(FX_SCHEMA, {"amount": 42.1, "from_currency": "EUR", "to_currency": "GBP"}) == []
    assert validate_input(FX_SCHEMA, {"amount": 0, "from_currency": "EUR", "to_currency": "GBP"}) == []


def test_every_error_is_reported_with_its_path():
    errors = validate_input(FX_SCHEMA, {"amount": "42.10", "from_currency": "eur", "fee": 1})
    text = " | ".join(errors)
    assert len(errors) == 4
    assert "missing required field 'to_currency'" in text
    assert "unexpected field 'fee'" in text
    assert "input.amount" in text and "input.from_currency" in text


def test_types_follow_json_not_python():
    assert validate_input({"type": "number"}, True) != []  # a JSON boolean is not a number
    assert validate_input({"type": "integer"}, False) != []
    assert validate_input({"type": "integer"}, 5.0) == []  # zero fractional part counts as an integer
    assert validate_input({"type": "integer"}, 5.5) != []
    assert validate_input({"type": ["string", "null"]}, None) == []
    assert validate_input({"type": "object"}, ["tx_1042"]) != []


def test_bounds_lengths_patterns_and_items():
    assert validate_input({"type": "number", "minimum": 0}, -0.01) != []
    assert validate_input({"type": "number", "maximum": 100}, 100) == []
    assert validate_input({"type": "string", "maxLength": 3}, "abcd") != []
    assert validate_input({"type": "string", "minLength": 1}, "") != []
    # JSON Schema patterns are not implicitly anchored
    assert validate_input({"type": "string", "pattern": "tx_[0-9]+"}, "see tx_1042") == []
    assert validate_input({"type": "string", "pattern": "^tx_[0-9]+$"}, "see tx_1042") != []
    errors = validate_input({"type": "array", "items": {"type": "string"}}, ["a", 2, "c"])
    assert errors and "[1]" in errors[0]


def test_registry_rejects_bad_definitions_listing_every_problem():
    reg = make_registry()
    with pytest.raises(ToolDefinitionError) as info:
        reg.register("look up", "Gets a transaction.", {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["tx"]}, print)
    message = str(info.value)
    for part in ("name", "description", "'tx'", "'id'"):
        assert part in message
    with pytest.raises(ToolDefinitionError):
        reg.register("get_transaction", DESC, TX_SCHEMA, print)  # duplicate
    with pytest.raises(ToolDefinitionError):
        reg.register("x" * 129, DESC, TX_SCHEMA, print)
    with pytest.raises(ToolDefinitionError):
        reg.register("lookup", DESC, {"type": "string"}, print)


def test_definitions_are_ordered_and_filtered_by_allow_list():
    reg = make_registry()
    assert reg.names() == ["get_transaction", "convert_currency", "issue_refund"]
    defs = reg.definitions()
    assert [d["name"] for d in defs] == ["get_transaction", "convert_currency", "issue_refund"]
    assert set(defs[0]) == {"name", "description", "input_schema"}
    assert defs[0]["input_schema"] == TX_SCHEMA
    allowed = reg.definitions(allowed=frozenset({"issue_refund", "get_transaction"}))
    assert [d["name"] for d in allowed] == ["get_transaction", "issue_refund"]
    assert reg.definitions(allowed=set()) == []
    assert reg.get("issue_refund").read_only is False and reg.get("nope") is None


def test_openai_shape_and_strict_requirements():
    reg = make_registry()
    tool = to_openai_tool(reg.definitions()[0], strict=True)
    assert tool == {"type": "function", "name": "get_transaction", "description": DESC, "parameters": TX_SCHEMA, "strict": True}
    loose = {"name": "find", "description": "x", "input_schema": {"type": "object", "properties": {"q": {"type": "string"}, "n": {"type": "integer"}}, "required": ["q"]}}
    assert to_openai_tool(loose)["strict"] is False
    with pytest.raises(ToolDefinitionError) as info:
        to_openai_tool(loose, strict=True)
    assert "additionalProperties" in str(info.value) and "n" in str(info.value)
    nested = {"name": "f", "description": "x", "input_schema": {"type": "object", "additionalProperties": False, "required": ["a"],
              "properties": {"a": {"type": "object", "properties": {"b": {"type": "string"}}, "required": ["b"]}}}}
    with pytest.raises(ToolDefinitionError):
        to_openai_tool(nested, strict=True)  # the nested object needs additionalProperties: false too


def test_tool_choice_per_provider():
    assert tool_choice_params("anthropic") == {"tool_choice": {"type": "auto"}}
    assert tool_choice_params("anthropic", "required") == {"tool_choice": {"type": "any"}}
    assert tool_choice_params("anthropic", "tool", "get_transaction") == {"tool_choice": {"type": "tool", "name": "get_transaction"}}
    assert tool_choice_params("anthropic", "none") == {"tool_choice": {"type": "none"}}
    assert tool_choice_params("anthropic", parallel=False) == {"tool_choice": {"type": "auto", "disable_parallel_tool_use": True}}
    assert tool_choice_params("openai") == {"tool_choice": "auto"}
    assert tool_choice_params("openai", "required") == {"tool_choice": "required"}
    assert tool_choice_params("openai", "tool", "get_transaction") == {"tool_choice": {"type": "function", "name": "get_transaction"}}
    assert tool_choice_params("openai", "none") == {"tool_choice": "none"}
    assert tool_choice_params("openai", parallel=False) == {"tool_choice": "auto", "parallel_tool_calls": False}
    for bad in (("anthropic", "tool", None), ("openai", "auto", "x"), ("anthropic", "always", None), ("gemini", "auto", None)):
        with pytest.raises(ValueError):
            tool_choice_params(*bad)
