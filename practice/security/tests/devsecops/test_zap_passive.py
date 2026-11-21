"""Checks exercises/devsecops/zap_passive.py: the rules on recorded responses, then on the loopback portal."""

import pytest
from devsecops.zap_passive import passive_alerts, passive_scan
from sandpay_vuln import make_app, serve

pytestmark = pytest.mark.exercise

URL = "http://127.0.0.1:9/page"
HTML = ("Content-Type", "text/html; charset=utf-8")
GOOD = [
    HTML,
    ("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'"),
    ("X-Content-Type-Options", "nosniff"),
]
STEPS = [
    ("GET", "/login", None),
    ("GET", "/search?q=sandpay", None),
    ("GET", "/boom", None),
    ("POST", "/api/login", {"email": "alice@shop-a.example", "password": "alice-pass-1"}),
]


def ids(alerts):
    return sorted(a.rule_id for a in alerts)


def test_a_well_configured_html_page_has_no_alerts():
    assert passive_alerts(URL, 200, GOOD, "<h1>ok</h1>") == []


def test_html_without_csp_or_framing_protection():
    alerts = passive_alerts(URL, 200, [HTML, ("X-Content-Type-Options", "nosniff")], "<h1>ok</h1>")
    assert ids(alerts) == ["10020-1", "10038-1"]
    assert {a.risk for a in alerts} == {"Medium"}


def test_x_frame_options_satisfies_the_clickjacking_rule():
    headers = [HTML, ("x-frame-options", "DENY"), ("X-Content-Type-Options", "nosniff")]
    assert ids(passive_alerts(URL, 200, headers, "")) == ["10038-1"]


def test_json_is_not_judged_for_html_only_rules():
    alerts = passive_alerts(URL, 404, [("Content-Type", "application/json")], '{"error": "not found"}')
    assert ids(alerts) == ["10021"]


def test_sniffing_header_must_say_nosniff():
    assert ids(passive_alerts(URL, 200, [("X-Content-Type-Options", "other")], "")) == ["10021"]


def test_server_version_is_reported_with_the_header_as_evidence():
    alerts = passive_alerts(URL, 200, GOOD + [("Server", "SandPayPortal/0.9 Python/3.12")], "")
    assert ids(alerts) == ["10036-2"]
    assert alerts[0].evidence == "SandPayPortal/0.9 Python/3.12"
    assert passive_alerts(URL, 200, GOOD + [("Server", "SandPay")], "") == []


def test_hsts_is_only_noise_on_plain_http():
    hsts = GOOD + [("Strict-Transport-Security", "max-age=31536000")]
    assert ids(passive_alerts("http://127.0.0.1:9/", 200, hsts, "")) == ["10035-4"]
    assert passive_alerts("https://shop.example/", 200, hsts, "") == []


def test_cookie_attributes_and_the_value_is_never_evidence():
    secret = "S3cretSessionValue"
    alerts = passive_alerts(URL, 200, GOOD + [("Set-Cookie", f"sid={secret}; Path=/")], "")
    assert ids(alerts) == ["10010", "10011", "10054-1"]
    assert {a.evidence for a in alerts} == {"sid"}
    assert secret not in repr(alerts)
    safe = "sid=x; Path=/; HttpOnly; Secure; SameSite=Lax"
    assert passive_alerts(URL, 200, GOOD + [("Set-Cookie", safe)], "") == []
    assert ids(passive_alerts(URL, 200, GOOD + [("Set-Cookie", "a=1; HttpOnly; Secure; samesite=Strict")], "")) == []


def test_each_cookie_is_judged_separately():
    headers = GOOD + [("Set-Cookie", "a=1; HttpOnly; Secure; SameSite=Lax"), ("Set-Cookie", "b=2; Secure; SameSite=Lax")]
    alerts = passive_alerts(URL, 200, headers, "")
    assert ids(alerts) == ["10010"]
    assert alerts[0].evidence == "b"


def test_error_disclosure_from_a_traceback():
    body = 'Traceback (most recent call last):\n  File "/srv/app.py", line 4, in run\n    boom()'
    alerts = passive_alerts(URL, 500, GOOD, body)
    assert ids(alerts) == ["90022"]
    assert alerts[0].risk == "Medium"
    assert alerts[0].evidence.startswith("Traceback")
    assert passive_alerts(URL, 500, GOOD, '{"error": "internal error", "reference": "a730b020"}') == []


def test_findings_carry_the_documented_name_and_risk():
    alert = passive_alerts(URL, 200, [HTML], "")[0]
    assert (alert.rule_id, alert.name, alert.risk) == ("10038-1", "Content Security Policy (CSP) Header Not Set", "Medium")
    assert alert.uri == URL


def test_vulnerable_portal_raises_the_expected_rules():
    with serve(make_app()) as base:
        alerts = passive_scan(base, STEPS)
    assert sorted({a.rule_id for a in alerts}) == [
        "10010", "10011", "10020-1", "10021", "10036-2", "10038-1", "10054-1", "90022",
    ]
    cookie = [a for a in alerts if a.rule_id == "10010"]
    assert len(cookie) == 1 and cookie[0].uri.endswith("/api/login") and cookie[0].evidence == "sid"
    assert [a.risk for a in alerts] == sorted((a.risk for a in alerts), key=["High", "Medium", "Low", "Informational"].index)


def test_scan_is_sorted_by_risk_then_rule_then_url():
    with serve(make_app()) as base:
        alerts = passive_scan(base, STEPS)
    order = {"Informational": 0, "Low": 1, "Medium": 2, "High": 3}
    keys = [(-order[a.risk], a.rule_id, a.uri) for a in alerts]
    assert keys == sorted(keys)


def test_fixed_portal_leaves_only_the_hsts_over_http_note():
    fixed = {"missing-headers", "weak-session", "verbose-errors"}
    with serve(make_app(fixed)) as base:
        alerts = passive_scan(base, STEPS)
    assert {a.rule_id for a in alerts} == {"10035-4"}
    assert {a.risk for a in alerts} == {"Informational"}


def test_the_scan_sends_only_the_steps_it_is_given():
    with serve(make_app()) as base:
        quiet = passive_scan(base, [("GET", "/login", None)])
        signed_in = passive_scan(base, [("POST", "/api/login", {"email": "alice@shop-a.example", "password": "alice-pass-1"})])
    assert not {a.rule_id for a in quiet} & {"10010", "10011", "10054-1", "90022"}
    assert {a.rule_id for a in signed_in} >= {"10010", "10011", "10054-1"}
    assert {a.evidence for a in signed_in if a.rule_id == "10010"} == {"sid"}


@pytest.mark.parametrize("target", ["http://203.0.113.9:8080", "http://127.0.0.1.evil.example", "https://shop.example"])
def test_refuses_anything_but_loopback_before_sending(target):
    with pytest.raises(ValueError):
        passive_scan(target, [("GET", "/", None)])
