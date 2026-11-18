import json

import pytest
from mcp.server_tools import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    ProtocolError,
    Tool,
    ToolError,
    ToolServer,
    decode_cursor,
    demo_ledger,
    encode_cursor,
    sandpay_tools,
)

pytestmark = pytest.mark.exercise

OBJ = {"type": "object", "properties": {}, "additionalProperties": False}


def make_server(page_size=2):
    server = ToolServer(page_size=page_size)
    ledger = demo_ledger()
    for tool in sandpay_tools(ledger):
        server.add_tool(tool)
    return server, ledger


def walk(server):
    """Follow nextCursor until the end, as a client would."""
    pages, cursor = [], None
    while True:
        result = server.list_tools({} if cursor is None else {"cursor": cursor})
        pages.append(result)
        cursor = result.get("nextCursor")
        if cursor is None:
            return pages


# --- add_tool -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["getUser", "DATA_EXPORT_v2", "admin.tools.list", "a" * 128])
def test_add_tool_accepts_spec_names(name):
    ToolServer().add_tool(Tool(name, "d", OBJ, lambda: "x"))


@pytest.mark.parametrize("name", ["", "get payment", "refund,all", "a" * 129, "tool/1"])
def test_add_tool_rejects_bad_names(name):
    with pytest.raises(ValueError):
        ToolServer().add_tool(Tool(name, "d", OBJ, lambda: "x"))


def test_add_tool_rejects_duplicates_and_non_object_schemas():
    server = ToolServer()
    server.add_tool(Tool("a", "d", OBJ, lambda: "x"))
    with pytest.raises(ValueError):
        server.add_tool(Tool("a", "d", OBJ, lambda: "y"))
    with pytest.raises(ValueError):
        server.add_tool(Tool("b", "d", {"type": "string"}, lambda: "x"))


# --- tools/list ---------------------------------------------------------------------------------------------


def test_first_page_is_sorted_and_has_cache_hints_and_a_cursor():
    server, _ = make_server()
    result = server.list_tools()
    assert [t["name"] for t in result["tools"]] == ["get_payment", "list_merchant_payments"]
    assert result["resultType"] == "complete"
    assert result["ttlMs"] == 300_000 and result["cacheScope"] == "public"
    assert isinstance(result["nextCursor"], str)


def test_walking_the_cursor_returns_every_tool_once_and_the_last_page_has_no_cursor():
    server, _ = make_server()
    pages = walk(server)
    names = [t["name"] for p in pages for t in p["tools"]]
    assert names == ["get_payment", "list_merchant_payments", "refund_payment"]
    assert len(pages) == 2 and "nextCursor" not in pages[-1]


def test_no_cursor_when_everything_fits_on_one_page():
    server, _ = make_server(page_size=10)
    assert "nextCursor" not in server.list_tools()


def test_order_is_deterministic_whatever_the_registration_order():
    a, b = ToolServer(page_size=10), ToolServer(page_size=10)
    for name in ["zeta", "alpha", "mid"]:
        a.add_tool(Tool(name, "d", OBJ, lambda: "x"))
    for name in ["mid", "zeta", "alpha"]:
        b.add_tool(Tool(name, "d", OBJ, lambda: "x"))
    assert a.list_tools() == b.list_tools()


def test_definitions_use_camel_case_and_hide_the_handler():
    server, _ = make_server(page_size=10)
    get_payment = server.list_tools()["tools"][0]
    assert set(get_payment) == {"name", "title", "description", "inputSchema", "outputSchema", "annotations"}
    listing = server.list_tools()["tools"][1]
    assert set(listing) == {"name", "description", "inputSchema", "annotations"}
    json.dumps(server.list_tools())  # must be JSON-serialisable: no functions inside


def test_cursor_round_trip_and_invalid_cursors():
    assert decode_cursor(encode_cursor(4)) == 4
    for bad in ["not-a-cursor!", 7, "", encode_cursor(2).upper()]:
        with pytest.raises(ProtocolError) as info:
            decode_cursor(bad)
        assert info.value.code == INVALID_PARAMS


def test_cursor_past_the_end_is_invalid_params():
    server, _ = make_server()
    with pytest.raises(ProtocolError) as info:
        server.list_tools({"cursor": encode_cursor(99)})
    assert info.value.code == INVALID_PARAMS


# --- tools/call: success ------------------------------------------------------------------------------------


def test_structured_result_has_text_copy_and_structured_content():
    server, _ = make_server()
    result = server.call_tool({"name": "get_payment", "arguments": {"payment_id": "pay_1042"}})
    assert result["resultType"] == "complete" and result["isError"] is False
    assert result["structuredContent"]["amount_minor"] == 8400
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]
    assert result["content"][0]["type"] == "text"


def test_plain_string_result_is_text_only():
    server, ledger = make_server()
    result = server.call_tool({"name": "refund_payment", "arguments": {"payment_id": "pay_1042", "amount_minor": 400}})
    assert result == {
        "resultType": "complete",
        "content": [{"type": "text", "text": "Refunded 400 EUR minor units on pay_1042; status partially_refunded."}],
        "isError": False,
    }
    assert ledger["pay_1042"]["refunded_minor"] == 400


def test_missing_arguments_means_empty_object():
    server = ToolServer()
    server.add_tool(Tool("ping_ledger", "d", OBJ, lambda: "ok"))
    assert server.call_tool({"name": "ping_ledger"})["content"][0]["text"] == "ok"


# --- tools/call: the two error paths ------------------------------------------------------------------------


def test_unknown_tool_is_a_protocol_error():
    server, _ = make_server()
    with pytest.raises(ProtocolError) as info:
        server.call_tool({"name": "delete_ledger", "arguments": {}})
    assert info.value.code == INVALID_PARAMS and info.value.message == "Unknown tool: delete_ledger"


@pytest.mark.parametrize("params", [None, [], {}, {"name": 5}, {"name": "get_payment", "arguments": "pay_1042"}])
def test_malformed_params_are_protocol_errors(params):
    server, _ = make_server()
    with pytest.raises(ProtocolError) as info:
        server.call_tool(params)
    assert info.value.code == INVALID_PARAMS


def test_invalid_arguments_are_a_tool_execution_error_and_the_handler_never_runs():
    server, ledger = make_server()
    result = server.call_tool({"name": "refund_payment", "arguments": {"payment_id": "1042", "amount_minor": 0, "x": 1}})
    assert result["isError"] is True and "structuredContent" not in result
    text = result["content"][0]["text"]
    assert text.startswith("Invalid arguments for refund_payment: ")
    assert "arguments.payment_id: does not match" in text
    assert "arguments.amount_minor: less than 1" in text
    assert "arguments.x: is not allowed" in text
    assert ledger["pay_1042"]["refunded_minor"] == 0


def test_tool_error_message_reaches_the_model():
    server, _ = make_server()
    result = server.call_tool({"name": "refund_payment", "arguments": {"payment_id": "pay_1042", "amount_minor": 9000}})
    assert result["isError"] is True
    assert result["content"][0]["text"] == "Refund of 9000 exceeds the refundable 8400 (EUR minor units) on pay_1042."


def test_crash_is_reported_without_internals_and_logged_for_the_operator():
    def broken(**kwargs):
        raise KeyError("SELECT * FROM ledger_internal WHERE id = 7")

    server = ToolServer()
    server.add_tool(Tool("get_report", "d", {"type": "object"}, broken))
    result = server.call_tool({"name": "get_report", "arguments": {}})
    assert result["isError"] is True
    assert result["content"][0]["text"] == "Tool get_report failed with an internal error"
    assert "SELECT" not in json.dumps(result)
    assert len(server.crashes) == 1 and "KeyError" in server.crashes[0]


def test_output_that_breaks_the_output_schema_is_a_server_error():
    server = ToolServer()
    schema = {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"]}
    server.add_tool(Tool("count", "d", OBJ, lambda: {"n": "three"}, output_schema=schema))
    with pytest.raises(ProtocolError) as info:
        server.call_tool({"name": "count", "arguments": {}})
    assert info.value.code == INTERNAL_ERROR
    assert server.crashes


def test_tool_error_class_is_an_exception():
    assert issubclass(ToolError, Exception)
