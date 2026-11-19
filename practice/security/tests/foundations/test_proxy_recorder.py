import http.client
import json

import pytest
from foundations.proxy_recorder import ProxyError, Target, clean_headers, in_scope, parse_target, run_proxy
from sandpay_vuln import make_app, serve

pytestmark = pytest.mark.exercise


# ---- parse_target ------------------------------------------------------------------------------------------
def test_absolute_form_with_port_and_query():
    t = parse_target("GET http://127.0.0.1:8765/api/payments?status=captured HTTP/1.1")
    assert t == Target("GET", "http", "127.0.0.1", 8765, "/api/payments?status=captured", "HTTP/1.1")


def test_absolute_form_defaults_port_80_and_root_path_and_lowercases_host():
    t = parse_target("GET http://Portal.SandPay.example HTTP/1.1")
    assert (t.host, t.port, t.path) == ("portal.sandpay.example", 80, "/")


def test_fragment_is_never_part_of_the_path():
    assert parse_target("GET http://127.0.0.1:1/a?b=1#frag HTTP/1.1").path == "/a?b=1"


def test_connect_authority_form():
    t = parse_target("CONNECT api.sandpay.example:443 HTTP/1.1")
    assert (t.method, t.scheme, t.host, t.port, t.path) == ("CONNECT", "", "api.sandpay.example", 443, "")


@pytest.mark.parametrize("line", [
    "GET /api/me HTTP/1.1",  # origin-form: meant for an origin server
    "CONNECT api.sandpay.example HTTP/1.1",  # no default port for CONNECT
    "GET ftp://127.0.0.1/file HTTP/1.1",
    "GET http:///nohost HTTP/1.1",
    "GET http://127.0.0.1:99999/ HTTP/1.1",
    "GET http://127.0.0.1/",
    "",
])
def test_rejects_what_a_proxy_cannot_serve(line):
    with pytest.raises(ProxyError) as err:
        parse_target(line)
    assert err.value.status == 400


# ---- in_scope ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("host,port,scope,expected", [
    ("127.0.0.1", 8765, ["127.0.0.1:8765"], True),
    ("127.0.0.1", 8766, ["127.0.0.1:8765"], False),
    ("127.0.0.1", 9000, ["127.0.0.1:*"], True),
    ("127.0.0.10", 8765, ["127.0.0.1:*"], False),
    ("evil-shop.example", 80, ["shop.example:*"], False),
    ("Shop.Example", 80, ["shop.example:80"], True),
    ("127.0.0.1", 8765, [], False),
])
def test_scope_matches_whole_hosts_only(host, port, scope, expected):
    assert in_scope(host, port, scope) is expected


# ---- clean_headers -----------------------------------------------------------------------------------------
T = Target("GET", "http", "127.0.0.1", 8765, "/api/me", "HTTP/1.1")


def test_removes_hop_by_hop_and_fields_named_in_connection():
    headers = [("Host", "wrong.example"), ("Connection", "keep-alive, X-Debug-Trace"), ("X-Debug-Trace", "1"),
               ("Keep-Alive", "timeout=5"), ("Proxy-Connection", "keep-alive"), ("TE", "trailers"),
               ("Upgrade", "websocket"), ("Authorization", "Bearer t"), ("Accept", "*/*")]
    out = clean_headers(headers, T)
    assert out == [("Host", "127.0.0.1:8765"), ("Authorization", "Bearer t"), ("Accept", "*/*"),
                   ("Via", "1.1 sandpay-recorder")]


def test_host_is_regenerated_from_the_target_and_port_80_is_omitted():
    t80 = Target("GET", "http", "portal.sandpay.example", 80, "/", "HTTP/1.1")
    assert clean_headers([("Accept", "*/*")], t80) == [("Accept", "*/*"), ("Host", "portal.sandpay.example"),
                                                       ("Via", "1.1 sandpay-recorder")]


def test_existing_via_is_extended_not_replaced():
    out = clean_headers([("Host", "x"), ("Via", "1.1 corp-gateway")], T)
    assert ("Via", "1.1 corp-gateway, 1.1 sandpay-recorder") in out
    assert sum(1 for n, _ in out if n.lower() == "via") == 1


def test_connection_option_names_are_case_insensitive():
    out = clean_headers([("connection", "X-Internal"), ("x-internal", "yes"), ("Host", "x")], T)
    assert [n for n, _ in out] == ["Host", "Via"]


# ---- the proxy end to end ----------------------------------------------------------------------------------
def via_proxy(proxy_url, method, absolute_url, headers=None, body=None):
    host, port = proxy_url.rsplit("//", 1)[1].split(":")
    conn = http.client.HTTPConnection(host, int(port), timeout=10)
    conn.request(method, absolute_url, body=body, headers=headers or {})
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r.status, data


def test_records_traffic_to_the_portal_and_relays_it_unchanged():
    with serve(make_app()) as base:
        port = int(base.rsplit(":", 1)[1])
        with run_proxy([f"127.0.0.1:{port}"]) as proxy:
            body = json.dumps({"email": "alice@shop-a.example", "password": "alice-pass-1"})
            status, data = via_proxy(proxy.url, "POST", base + "/api/login", {"Content-Type": "application/json"},
                                     body)
            assert status == 200
            token = json.loads(data)["token"]
            status, data = via_proxy(proxy.url, "GET", base + "/api/payments/pay_1001",
                                     {"Authorization": f"Bearer {token}", "Proxy-Connection": "keep-alive"})
            assert status == 200 and json.loads(data)["id"] == "pay_1001"
            assert [(x.method, x.url, x.status) for x in proxy.history] == [
                ("POST", base + "/api/login", 200), ("GET", base + "/api/payments/pay_1001", 200)]
            sent = dict((n.lower(), v) for n, v in proxy.history[1].request_headers)
            assert sent["host"] == f"127.0.0.1:{port}" and sent["via"] == "1.1 sandpay-recorder"
            assert "proxy-connection" not in sent
            assert proxy.history[0].request_body == body.encode()


def test_out_of_scope_and_connect_are_refused_and_not_recorded():
    with serve(make_app()) as base:
        with run_proxy(["127.0.0.1:1"]) as proxy:
            assert via_proxy(proxy.url, "GET", base + "/health")[0] == 403
            assert via_proxy(proxy.url, "CONNECT", "api.sandpay.example:443")[0] == 501
            assert via_proxy(proxy.url, "GET", "/health")[0] == 400
            assert proxy.history == []
