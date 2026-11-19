import json

import pytest
from foundations.proxy_repeater import (
    RecordedRequest,
    Reply,
    diff,
    parse_raw_request,
    probe_idor,
    send,
    with_path_segment,
)
from sandpay_vuln import make_app, serve

pytestmark = pytest.mark.exercise


# ---- parse_raw_request -------------------------------------------------------------------------------------
def test_parses_crlf_request_with_json_body_and_content_length():
    raw = ("POST /api/notes HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nAuthorization: Bearer abc\r\n"
           "Content-Type: application/json\r\nContent-Length: 15\r\n\r\n{\"body\": \"hi\"}\nTRAILING")
    req = parse_raw_request(raw)
    assert req.method == "POST" and req.url == "http://127.0.0.1:8765/api/notes"
    assert req.headers[0] == ("Host", "127.0.0.1:8765") and ("Authorization", "Bearer abc") in req.headers
    assert req.body == b'{"body": "hi"}\n'


def test_parses_lf_only_absolute_form_and_keeps_header_case_and_order():
    raw = "GET http://127.0.0.1:9/search?q=x HTTP/1.1\nX-Trace:   7  \nhost: 127.0.0.1:9\n\n"
    req = parse_raw_request(raw)
    assert req.url == "http://127.0.0.1:9/search?q=x"
    assert req.headers == (("X-Trace", "7"), ("host", "127.0.0.1:9")) and req.body == b""


@pytest.mark.parametrize("raw", ["GET /x\n\n", "GET /x HTTP/1.1\nNoColonHere\n\n", "GET /x HTTP/1.1\n\n",
                                 "GET /x HTTP/1.1\n Bad: indent\n\n"])
def test_rejects_malformed_requests(raw):
    with pytest.raises(ValueError):
        parse_raw_request(raw)


# ---- with_path_segment -------------------------------------------------------------------------------------
def test_swaps_whole_segments_only_and_keeps_query():
    req = RecordedRequest("GET", "http://127.0.0.1:1/api/payments/pay_1001?expand=pay_1001", ())
    assert with_path_segment(req, "pay_1001", "pay_2001").url == "http://127.0.0.1:1/api/payments/pay_2001?expand=pay_1001"
    longer = RecordedRequest("GET", "http://127.0.0.1:1/api/payments/pay_10010", ())
    with pytest.raises(ValueError):
        with_path_segment(longer, "pay_1001", "pay_2001")
    assert req.url.endswith("pay_1001?expand=pay_1001")  # the original is unchanged


# ---- diff --------------------------------------------------------------------------------------------------
def reply(status, obj=None, body=None):
    return Reply(status, {}, body if body is not None else json.dumps(obj).encode())


def test_diff_json_objects_by_key():
    a = reply(200, {"id": "pay_1001", "merchant_id": "m_100", "api_secret": "s"})
    b = reply(404, {"id": "pay_1001", "merchant_id": "m_200", "error": "payment not found"})
    assert diff(a, b) == ["status 200 -> 404", "json api_secret: removed", "json error: added 'payment not found'",
                          "json merchant_id: 'm_100' -> 'm_200'"]


def test_diff_non_json_and_identical():
    assert diff(reply(200, body=b"<h1>a</h1>"), reply(200, body=b"<h1>abc</h1>")) == ["body changed (10 -> 12 bytes)"]
    assert diff(reply(200, {"a": 1}), reply(200, {"a": 1})) == []


# ---- probe_idor against the portal -------------------------------------------------------------------------
def login(base):
    raw = ("POST /api/login HTTP/1.1\nHost: {h}\nContent-Type: application/json\n\n"
           '{{"email": "alice@shop-a.example", "password": "alice-pass-1"}}').format(h=base.split("//")[1])
    return send(parse_raw_request(raw)).json()["token"]


def recorded_get(base, token, pid="pay_1001"):
    return parse_raw_request(f"GET /api/payments/{pid} HTTP/1.1\nHost: {base.split('//')[1]}\n"
                             f"Authorization: Bearer {token}\n\n")


def test_probe_finds_idor_in_the_vulnerable_portal():
    with serve(make_app()) as base:
        finding = probe_idor(recorded_get(base, login(base)), "pay_1001", "pay_2001")
    assert finding is not None
    assert finding.title == "IDOR: pay_2001 readable by the owner of pay_1001"
    assert finding.replayed.status == 200 and "json merchant_id: 'm_100' -> 'm_200'" in finding.changes


def test_probe_is_quiet_when_access_control_is_fixed():
    with serve(make_app({"idor"})) as base:
        assert probe_idor(recorded_get(base, login(base)), "pay_1001", "pay_2001") is None


def test_probe_is_quiet_when_the_other_id_is_also_the_callers():
    with serve(make_app()) as base:
        assert probe_idor(recorded_get(base, login(base)), "pay_1001", "pay_1002") is None


def test_probe_refuses_to_judge_when_the_original_request_fails():
    with serve(make_app()) as base:
        with pytest.raises(ValueError):
            probe_idor(recorded_get(base, "not-a-token"), "pay_1001", "pay_2001")
