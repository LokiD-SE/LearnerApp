import html
from html.parser import HTMLParser

import pytest
import requests
from sandpay_vuln import make_app, serve
from web.xss_encode import encode_html_text, encode_url_param, render_attribute, safe_href

pytestmark = pytest.mark.exercise

PAYLOADS = [
    "<script>alert(1)</script>",
    '"><img src=x onerror=alert(1)>',
    "' onmouseover='alert(1)",
    "Tom & Jerry's <b>\"shop\"</b>",
    "&lt;already encoded&gt;",
]


class TagCounter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.attrs = [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend(attrs)


def parse(markup):
    p = TagCounter()
    p.feed(markup)
    p.close()
    return p


def test_cheat_sheet_table():
    assert encode_html_text("&<>\"'") == "&amp;&lt;&gt;&quot;&#x27;"
    assert encode_html_text("plain text 123") == "plain text 123"


def test_ampersand_is_encoded_once():
    assert encode_html_text("&lt;") == "&amp;lt;"
    assert encode_html_text("a & b") == "a &amp; b"


@pytest.mark.parametrize("payload", PAYLOADS)
def test_text_context_adds_no_markup_and_round_trips(payload):
    page = parse(f"<p>{encode_html_text(payload)}</p>")
    assert page.tags == ["p"]
    assert html.unescape(encode_html_text(payload)) == payload


@pytest.mark.parametrize("payload", PAYLOADS)
def test_attribute_value_cannot_escape_its_quotes(payload):
    page = parse(f"<input {render_attribute('value', payload)}>")
    assert page.tags == ["input"]
    assert page.attrs == [("value", payload)]


def test_attribute_names_are_fixed():
    assert render_attribute("title", "x") == 'title="x"'
    for bad in ("onclick", "onmouseover", "style", "srcdoc", 'title" onclick="x'):
        with pytest.raises(ValueError):
            render_attribute(bad, "x")


def test_url_parameter_encoding():
    assert encode_url_param("a b&c=d/é") == "a%20b%26c%3Dd%2F%C3%A9"
    assert encode_url_param("plain-text_1.0~") == "plain-text_1.0~"


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://shop-a.example/orders?id=7", "https://shop-a.example/orders?id=7"),
        ("HTTPS://Shop-A.example/", "HTTPS://Shop-A.example/"),
        ("/notes?x=1&y=2", "/notes?x=1&amp;y=2"),
        ('https://shop-a.example/?q="x"', "https://shop-a.example/?q=&quot;x&quot;"),
        ("javascript:alert(1)", "#"),
        (" JaVaScRiPt:alert(1)", "#"),
        ("java\tscript:alert(1)", "#"),
        ("java\nscript:alert(1)", "#"),
        ("\x01javascript:alert(1)", "#"),
        ("data:text/html,hello", "#"),
        ("vbscript:x", "#"),
        ("//evil.example/", "#"),
        ("/\\evil.example/", "#"),
        ("https:evil.example", "#"),
    ],
)
def test_safe_href(url, expected):
    assert safe_href(url) == expected


def test_matches_the_fixed_portal():
    # The fixed portal's search page encodes with the same five entities - a fix a tester can verify.
    payload = "<b title=\"x\">Tom & Jerry's</b>"
    with serve(make_app({"xss-reflected"})) as base:
        page = requests.get(base + "/search", params={"q": payload}, timeout=5).text
    assert f"Results for {encode_html_text(payload)}</h1>" in page
