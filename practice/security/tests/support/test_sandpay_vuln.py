"""Checks the shared practice app itself: every flaw is exploitable when present and closed when fixed.

Not a learner exercise (verify.py skips tests/support); it guards the target the exercises rely on.
"""

import http.client
import json
import urllib.parse

import pytest
from sandpay_vuln import FLAWS, make_app, make_jwt, serve


def call(base, method, path, body=None, headers=None, form=False):
    u = urllib.parse.urlsplit(base)
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=5)
    hdrs = dict(headers or {})
    data = None
    if body is not None:
        if form:
            data = urllib.parse.urlencode(body).encode()
            hdrs["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body).encode()
            hdrs["Content-Type"] = "application/json"
    conn.request(method, path, body=data, headers=hdrs)
    r = conn.getresponse()
    text = r.read().decode()
    conn.close()
    return r.status, {k.lower(): v for k, v in r.getheaders()}, text


def login(base, email="alice@shop-a.example", password="alice-pass-1"):
    status, headers, text = call(base, "POST", "/api/login", {"email": email, "password": password})
    assert status == 200, text
    sid = headers["set-cookie"].split(";")[0]
    return json.loads(text)["token"], sid, headers["set-cookie"]


@pytest.fixture(params=["vulnerable", "fixed"])
def portal(request):
    app = make_app() if request.param == "vulnerable" else make_app(FLAWS)
    with serve(app) as base:
        yield request.param == "vulnerable", base, app


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_idor(portal):
    vuln, base, _ = portal
    token, _, _ = login(base)
    status, _, _ = call(base, "GET", "/api/payments/pay_2001", headers=bearer(token))
    assert status == (200 if vuln else 404)


def test_mass_assignment(portal):
    vuln, base, _ = portal
    token, _, _ = login(base)
    status, _, text = call(base, "PATCH", "/api/profile", {"display_name": "A", "role": "admin"}, bearer(token))
    if vuln:
        assert status == 200 and json.loads(text)["role"] == "admin"
    else:
        assert status == 400


def test_sqli(portal):
    vuln, base, _ = portal
    token, _, _ = login(base)
    q = urllib.parse.quote("x' OR '1'='1")
    status, _, text = call(base, "GET", f"/api/payments?status={q}", headers=bearer(token))
    ids = {p["merchant_id"] for p in json.loads(text)["data"]} if status == 200 else set()
    assert ("m_200" in ids) == vuln


def test_xss_reflected(portal):
    vuln, base, _ = portal
    _, _, text = call(base, "GET", "/search?q=" + urllib.parse.quote("<script>alert(1)</script>"))
    assert ("<script>alert(1)</script>" in text) == vuln


def test_xss_stored(portal):
    vuln, base, _ = portal
    token, _, _ = login(base)
    call(base, "POST", "/api/notes", {"body": "<img src=x onerror=alert(1)>"}, bearer(token))
    _, _, text = call(base, "GET", "/notes", headers=bearer(token))
    assert ("<img src=x onerror=alert(1)>" in text) == vuln


def test_path_traversal(portal):
    vuln, base, _ = portal
    _, _, text = call(base, "GET", "/files?name=" + urllib.parse.quote("../internal/settlement-keys.txt"))
    assert ("SETTLEMENT_SIGNING_KEY" in text) == vuln
    status, _, _ = call(base, "GET", "/files?name=terms.txt")
    assert status == 200


def test_open_redirect(portal):
    vuln, base, _ = portal
    status, headers, _ = call(base, "GET", "/login?next=" + urllib.parse.quote("https://evil.example/"))
    assert status == 302
    assert (headers["location"] == "https://evil.example/") == vuln


def test_ssrf(portal):
    vuln, base, _ = portal
    token, _, _ = login(base)
    status, _, text = call(base, "POST", "/api/webhooks/test", {"url": base + "/internal/admin"}, bearer(token))
    assert ("settlement_key" in text) == vuln
    if not vuln:
        assert status == 400


def test_csrf(portal):
    vuln, base, _ = portal
    _, sid, _ = login(base)
    status, _, _ = call(base, "POST", "/settings/email", {"email": "attacker@evil.example"}, {"Cookie": sid}, form=True)
    assert status == (200 if vuln else 403)


def test_weak_session_cookie(portal):
    vuln, base, _ = portal
    _, _, cookie = login(base)
    flags = cookie.lower()
    assert ("httponly" not in flags and "samesite" not in flags) == vuln


def test_rate_limit(portal):
    vuln, base, _ = portal
    statuses = [call(base, "POST", "/api/login", {"email": "alice@shop-a.example", "password": f"guess-{i}"})[0]
                for i in range(7)]
    assert (429 in statuses) != vuln


def test_jwt_none(portal):
    vuln, base, _ = portal
    forged = make_jwt({"sub": "ops@sandpay.example"}, alg="none")
    status, _, text = call(base, "GET", "/api/me", headers=bearer(forged))
    if vuln:
        assert status == 200 and json.loads(text)["role"] == "admin"
    else:
        assert status == 401


def test_weak_hash(portal):
    vuln, _, app = portal
    stored = app.query("SELECT password_hash FROM users WHERE email = 'alice@shop-a.example'")[0][0]
    assert (len(stored) == 32 and stored.isalnum()) == vuln


def test_verbose_errors(portal):
    vuln, base, _ = portal
    status, _, text = call(base, "GET", "/boom")
    assert status == 500
    assert ("Traceback" in text) == vuln


def test_security_headers(portal):
    vuln, base, _ = portal
    _, headers, _ = call(base, "GET", "/health")
    assert ("content-security-policy" not in headers) == vuln
    assert ("server" in headers and "Python" in headers["server"]) == vuln


def test_data_exposure(portal):
    vuln, base, _ = portal
    token, _, _ = login(base)
    _, _, text = call(base, "GET", "/api/merchants/m_100", headers=bearer(token))
    assert ("api_secret" in text) == vuln


def test_secret_logging(portal):
    vuln, base, app = portal
    login(base)
    assert any("password=" in line for line in app.access_log) == vuln


def test_refuses_non_loopback():
    with pytest.raises(ValueError):
        with serve(make_app(), host="0.0.0.0"):
            pass


def test_every_flaw_has_a_test():
    names = {n for n in globals() if n.startswith("test_")}
    assert len(FLAWS) == 17 and len(names) >= 17
