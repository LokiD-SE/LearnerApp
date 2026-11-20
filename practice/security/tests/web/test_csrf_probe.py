import pytest
import requests
from sandpay_vuln import HttpError, make_app, serve
from web.csrf_probe import Form, forged_bodies, probe_csrf, token_fields

pytestmark = pytest.mark.exercise

NEW = "attacker@evil.example"


def sign_in(base, email="alice@shop-a.example", password="alice-pass-1"):
    r = requests.post(base + "/api/login", json={"email": email, "password": password}, timeout=5)
    r.raise_for_status()
    return r.headers["Set-Cookie"].split(";")[0]  # "sid=..." - sent by hand, see the exercise docstring


def email_of(base, cookie):
    return requests.get(base + "/api/me", headers={"Cookie": cookie}, timeout=5).json()["email"]


def test_token_fields_by_name():
    form = Form("/x", "POST", {"email": "", "csrf": "a", "authenticity_token": "b", "X-XSRF": "c", "note": ""})
    assert token_fields(form) == ["X-XSRF", "authenticity_token", "csrf"]


def test_forgeries_without_a_token_field():
    form = Form("/settings/email", "POST", {"email": ""})
    assert forged_bodies(form, {"email": NEW}) == {"no-token": {"email": NEW}}


def test_forgeries_with_a_token_field():
    form = Form("/settings/email", "POST", {"csrf": "real-token", "email": ""})
    bodies = forged_bodies(form, {"email": NEW})
    assert set(bodies) == {"no-token", "empty-token", "wrong-token"}
    assert bodies["no-token"] == {"email": NEW}
    assert bodies["empty-token"] == {"csrf": "", "email": NEW}
    assert bodies["wrong-token"]["email"] == NEW
    assert bodies["wrong-token"]["csrf"] not in ("", "real-token")
    assert form.fields == {"csrf": "real-token", "email": ""}  # the captured form is not modified


def test_finds_csrf_on_the_vulnerable_portal():
    with serve(make_app()) as base:
        cookie = sign_in(base)
        result = probe_csrf(base, cookie, NEW)
        assert result.verdict == "vulnerable"
        assert result.token_fields == []
        assert [(a.name, a.status, a.changed) for a in result.attempts] == [
            ("control", 200, True), ("no-token", 200, True)]
        assert result.restored and email_of(base, cookie) == "alice@shop-a.example"  # left as found


@pytest.mark.parametrize("fixed", [{"csrf"}, {"csrf", "weak-session"}])
def test_quiet_once_csrf_is_fixed(fixed):
    with serve(make_app(fixed)) as base:
        cookie = sign_in(base)
        result = probe_csrf(base, cookie, NEW)
        assert result.verdict == "not-vulnerable"
        assert result.token_fields == ["csrf"]
        assert [(a.name, a.status, a.changed) for a in result.attempts] == [
            ("control", 200, True), ("no-token", 403, False), ("empty-token", 403, False),
            ("wrong-token", 403, False)]
        assert result.restored and email_of(base, cookie) == "alice@shop-a.example"


def test_inconclusive_when_the_control_fails():
    # The form handler is broken for everybody - a 503 for the forgery would prove nothing about CSRF.
    app = make_app()

    def broken(req):
        raise HttpError(503, "email service unavailable")

    app.routes = [(m, p, broken if p == "/settings/email" else fn) for m, p, fn in app.routes]
    with serve(app) as base:
        cookie = sign_in(base)
        result = probe_csrf(base, cookie, NEW)
        assert result.verdict == "inconclusive"
        assert [(a.name, a.status, a.changed) for a in result.attempts] == [("control", 503, False)]


def test_other_users_are_untouched():
    with serve(make_app()) as base:
        alice, bob = sign_in(base), sign_in(base, "bob@shop-b.example", "bob-pass-2")
        probe_csrf(base, alice, NEW)
        assert email_of(base, bob) == "bob@shop-b.example"
