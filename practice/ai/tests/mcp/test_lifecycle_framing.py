import json

import pytest
from mcp.lifecycle_framing import INVALID_REQUEST, PARSE_ERROR, FramingError, LineDecoder, classify, encode_message

pytestmark = pytest.mark.exercise

LOOKUP = {
    "jsonrpc": "2.0",
    "id": 7,
    "method": "tools/call",
    "params": {"name": "find_merchant", "arguments": {"query": "Café Rosa\nline two"}},
}


def test_encode_is_one_compact_line_ending_in_newline():
    frame = encode_message(LOOKUP)
    assert frame.endswith(b"\n")
    assert frame.count(b"\n") == 1
    assert b": " not in frame and b", " not in frame


def test_encode_escapes_newlines_inside_strings():
    frame = encode_message(LOOKUP)
    assert b"\\n" in frame
    assert json.loads(frame) == LOOKUP


def test_encode_keeps_utf8_instead_of_ascii_escapes():
    frame = encode_message(LOOKUP)
    assert "Café".encode("utf-8") in frame
    assert b"\\u00e9" not in frame


def test_encode_rejects_non_objects():
    with pytest.raises(FramingError):
        encode_message([LOOKUP])


@pytest.mark.parametrize(
    "message, kind",
    [
        ({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, "request"),
        ({"jsonrpc": "2.0", "id": "a-1", "method": "tools/list"}, "request"),
        ({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1}}, "notification"),
        ({"jsonrpc": "2.0", "id": 1, "result": {"resultType": "complete"}}, "result"),
        ({"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "Method not found"}}, "error"),
        ({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}, "error"),
        ({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}, "error"),
    ],
)
def test_classify_valid(message, kind):
    assert classify(message) == (kind, "")


@pytest.mark.parametrize(
    "message, reason",
    [
        ([1, 2], "not an object"),
        ({"id": 1, "method": "ping"}, "jsonrpc must be '2.0'"),
        ({"jsonrpc": "2.0", "id": 1, "method": 5}, "method must be a string"),
        ({"jsonrpc": "2.0", "id": None, "method": "ping"}, "id must be a string or integer"),
        ({"jsonrpc": "2.0", "id": True, "method": "ping"}, "id must be a string or integer"),
        ({"jsonrpc": "2.0", "id": 1.5, "method": "ping"}, "id must be a string or integer"),
        ({"jsonrpc": "2.0", "id": 1, "result": {}, "error": {"code": 1, "message": "x"}}, "result and error are exclusive"),
        ({"jsonrpc": "2.0", "id": None, "result": {}}, "id must be a string or integer"),
        ({"jsonrpc": "2.0", "id": 1, "error": {"code": "-32600", "message": "x"}}, "error needs integer code and string message"),
        ({"jsonrpc": "2.0", "id": 1}, "no method, result or error"),
    ],
)
def test_classify_invalid(message, reason):
    assert classify(message) == ("invalid", reason)


def test_decoder_waits_for_the_newline():
    dec = LineDecoder()
    frame = encode_message({"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert dec.feed(frame[:10]) == []
    assert dec.pending == 10
    frames = dec.feed(frame[10:])
    assert [f.kind for f in frames] == ["request"]
    assert dec.pending == 0


def test_decoder_returns_every_complete_line_in_one_chunk():
    dec = LineDecoder()
    data = encode_message({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + encode_message(
        {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1}}
    ) + b'{"jsonrpc":"2.0"'
    frames = dec.feed(data)
    assert [f.kind for f in frames] == ["request", "notification"]
    assert dec.pending == len(b'{"jsonrpc":"2.0"')


def test_decoder_survives_a_utf8_character_split_across_chunks():
    dec = LineDecoder()
    frame = encode_message(LOOKUP)
    cut = frame.index("é".encode("utf-8")) + 1  # between the two bytes of é
    assert dec.feed(frame[:cut]) == []
    frames = dec.feed(frame[cut:])
    assert frames[0].message == LOOKUP


def test_decoder_strips_a_trailing_carriage_return():
    frames = LineDecoder().feed(b'{"jsonrpc":"2.0","id":3,"method":"ping"}\r\n')
    assert frames[0].kind == "request"
    assert frames[0].message["id"] == 3


def test_decoder_reports_parse_errors_and_keeps_going():
    frames = LineDecoder().feed(b'{"jsonrpc":"2.0","id":1,\n{"jsonrpc":"2.0","id":2,"method":"ping"}\n')
    assert frames[0].kind == "invalid"
    assert frames[0].message is None
    assert frames[0].error == {"jsonrpc": "2.0", "id": None, "error": {"code": PARSE_ERROR, "message": "Parse error"}}
    assert frames[1].kind == "request"


def test_decoder_reports_invalid_utf8_as_parse_error():
    frames = LineDecoder().feed(b'{"jsonrpc":"2.0","id":1,"method":"\xff"}\n')
    assert frames[0].error["error"]["code"] == PARSE_ERROR


def test_decoder_reports_invalid_requests_with_the_id_when_readable():
    frames = LineDecoder().feed(b'{"jsonrpc":"1.0","id":9,"method":"ping"}\n{"jsonrpc":"2.0","id":null,"method":"ping"}\n')
    assert frames[0].error == {
        "jsonrpc": "2.0",
        "id": 9,
        "error": {"code": INVALID_REQUEST, "message": "Invalid Request", "data": "jsonrpc must be '2.0'"},
    }
    assert frames[1].error["id"] is None
    assert frames[1].error["error"]["data"] == "id must be a string or integer"
