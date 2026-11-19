import json
from datetime import datetime, timedelta, timezone

import pytest
from foundations.proxy_evidence import MASK, redact, to_har
from proxy_fixture import Exchange

pytestmark = pytest.mark.exercise

T0 = datetime(2026, 11, 19, 9, 15, 2, 481000, tzinfo=timezone.utc)


def login_exchange():
    return Exchange(
        started=T0 + timedelta(seconds=1), method="POST", url="http://127.0.0.1:8765/api/login?lang=en&debug=",
        http_version="HTTP/1.1",
        request_headers=[("Host", "127.0.0.1:8765"), ("Content-Type", "application/json"),
                         ("Cookie", "theme=dark; sid=abc123")],
        request_body=b'{"email": "alice@shop-a.example", "password": "alice-pass-1"}',
        status=200, reason="OK",
        response_headers=[("Content-Type", "application/json"), ("Set-Cookie", "sid=s3cr3t; Path=/; HttpOnly")],
        response_body=b'{"token": "eyJabc", "merchant_id": "m_100", "role": "merchant"}',
        send_ms=0.2504, wait_ms=3.1, receive_ms=0.05, notes=["login as alice"])


def redirect_exchange():
    return Exchange(
        started=T0, method="GET", url="http://127.0.0.1:8765/login?next=https%3A%2F%2Fevil.example%2F#top",
        http_version="HTTP/1.1", request_headers=[("Host", "127.0.0.1:8765")], request_body=b"",
        status=302, reason="Found", response_headers=[("Location", "https://evil.example/")], response_body=b"",
        send_ms=0.1, wait_ms=1.2, receive_ms=0.0)


def test_log_shape_and_entry_order():
    har = to_har([login_exchange(), redirect_exchange()], "sandpay-recorder", "1.0")
    log = har["log"]
    assert log["version"] == "1.2" and log["creator"] == {"name": "sandpay-recorder", "version": "1.0"}
    assert "pages" not in log
    assert [e["request"]["method"] for e in log["entries"]] == ["GET", "POST"]  # oldest first
    json.dumps(har)  # serialisable


def test_entry_times_sum_and_iso_timestamp():
    e = to_har([login_exchange()])["log"]["entries"][0]
    assert e["startedDateTime"] == "2026-11-19T09:15:03.481Z"
    assert e["timings"] == {"send": 0.25, "wait": 3.1, "receive": 0.05}
    assert e["time"] == pytest.approx(3.4)
    assert e["cache"] == {} and e["comment"] == "login as alice"


def test_request_fields():
    r = to_har([login_exchange()])["log"]["entries"][0]["request"]
    assert r["url"] == "http://127.0.0.1:8765/api/login?lang=en&debug="
    assert r["httpVersion"] == "HTTP/1.1"
    assert r["queryString"] == [{"name": "lang", "value": "en"}, {"name": "debug", "value": ""}]
    assert r["cookies"] == [{"name": "theme", "value": "dark"}, {"name": "sid", "value": "abc123"}]
    assert r["headers"][1] == {"name": "Content-Type", "value": "application/json"}
    assert r["headersSize"] == -1 and r["bodySize"] == len(login_exchange().request_body)
    assert r["postData"] == {"mimeType": "application/json", "text": login_exchange().request_body.decode()}


def test_response_fields_and_redirect():
    entries = to_har([login_exchange(), redirect_exchange()])["log"]["entries"]
    redirect, login = entries
    assert redirect["request"]["url"].endswith("next=https%3A%2F%2Fevil.example%2F")  # fragment dropped
    assert "postData" not in redirect["request"]
    assert redirect["response"]["redirectURL"] == "https://evil.example/"
    assert redirect["response"]["status"] == 302 and redirect["response"]["statusText"] == "Found"
    resp = login["response"]
    assert resp["cookies"] == [{"name": "sid", "value": "s3cr3t", "httpOnly": True, "secure": False, "path": "/"}]
    assert resp["content"] == {"size": len(login_exchange().response_body), "mimeType": "application/json",
                               "text": login_exchange().response_body.decode()}
    assert resp["redirectURL"] == "" and resp["headersSize"] == -1 and "comment" not in redirect


def test_redact_masks_secrets_and_keeps_evidence():
    har = to_har([login_exchange()])
    before = json.dumps(har)
    clean = redact(har)
    assert json.dumps(har) == before  # input untouched
    e = clean["log"]["entries"][0]
    text = json.dumps(clean)
    for secret in ("alice-pass-1", "abc123", "s3cr3t", "eyJabc"):
        assert secret not in text, secret
    assert json.loads(e["request"]["postData"]["text"]) == {"email": "alice@shop-a.example", "password": MASK}
    assert json.loads(e["response"]["content"]["text"])["merchant_id"] == "m_100"
    assert {"name": "Cookie", "value": MASK} in e["request"]["headers"]
    assert {"name": "Set-Cookie", "value": MASK} in e["response"]["headers"]
    assert e["response"]["cookies"][0]["httpOnly"] is True  # the flags are the evidence
    assert e["response"]["status"] == 200 and e["request"]["url"] == login_exchange().url.split("#")[0]


def test_redact_form_bodies_and_query_strings_and_nested_json():
    x = login_exchange()
    x.request_headers = [("Content-Type", "application/x-www-form-urlencoded")]
    x.request_body = b"email=a%40b.example&password=hunter2&csrf=tok"
    x.url = "http://127.0.0.1:8765/api/login?token=abc&page=2"
    x.response_body = b'{"data": [{"id": "m_100", "api_secret": "sk_x"}]}'
    clean = redact(to_har([x]))["log"]["entries"][0]
    assert "hunter2" not in clean["request"]["postData"]["text"] and "a%40b.example" in clean["request"]["postData"]["text"]
    assert clean["request"]["queryString"] == [{"name": "token", "value": MASK}, {"name": "page", "value": "2"}]
    assert json.loads(clean["response"]["content"]["text"]) == {"data": [{"id": "m_100", "api_secret": MASK}]}
