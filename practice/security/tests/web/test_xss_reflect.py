import re

import pytest
import requests
from sandpay_vuln import make_app, serve
from web.xss_reflect import (
    BREAKOUT,
    PROBE_CHARS,
    classify_context,
    find_reflected_xss,
    make_canary,
    probe_characters,
)

pytestmark = pytest.mark.exercise


def test_canary_is_unique_and_alphanumeric():
    a, b = make_canary(), make_canary()
    assert a != b
    assert re.fullmatch(r"[a-z0-9]{8,}", a), a


@pytest.mark.parametrize(
    "page, context",
    [
        ("<h1>Results for CANARY</h1>", "html-text"),
        ('<input name="q" value="abc CANARY">', "attribute-double"),
        ("<input name='q' value='CANARY'>", "attribute-single"),
        ("<input name=q value=CANARY>", "attribute-unquoted"),
        ('<script>var q = "CANARY";</script>', "script"),
        ("<!-- searched for CANARY -->", "comment"),
        ('<script src="/app.js"></script><p>CANARY</p>', "html-text"),
        ('<a title="x" href="/s">CANARY</a>', "html-text"),
    ],
)
def test_classify_context(page, context):
    assert classify_context(page, "CANARY") == context


def test_classify_context_missing():
    assert classify_context("<p>nothing here</p>", "CANARY") is None


def test_breakout_table_covers_every_context():
    assert set(BREAKOUT) == {"html-text", "attribute-double", "attribute-single", "attribute-unquoted", "script", "comment"}
    assert "<" in PROBE_CHARS and '"' in PROBE_CHARS


def test_vulnerable_search_reflects_angle_brackets_raw():
    with serve(make_app()) as base:
        report = probe_characters(base, "/search", "q")
    assert report.context == "html-text"
    assert report.fates["<"] == "raw" and report.fates[">"] == "raw"
    assert report.breakout_chars == ["<"]


def test_fixed_search_encodes_everything():
    with serve(make_app({"xss-reflected"})) as base:
        report = probe_characters(base, "/search", "q")
    assert report.context == "html-text"
    for char in ("<", ">", '"', "'", "&"):
        assert report.fates[char] == "encoded", (char, report.fates)
    assert report.breakout_chars == []


def test_finding_on_vulnerable_portal():
    with serve(make_app()) as base:
        finding = find_reflected_xss(base, "/search", "q")
    assert finding is not None
    assert finding.context == "html-text" and finding.breakout_chars == ["<"]
    assert "<h1>Results for" in finding.evidence and "<" in finding.evidence


def test_no_finding_when_fixed():
    with serve(make_app({"xss-reflected"})) as base:
        assert find_reflected_xss(base, "/search", "q") is None


def test_no_finding_for_a_parameter_that_is_not_reflected():
    with serve(make_app()) as base:
        assert find_reflected_xss(base, "/search", "page") is None


def test_probe_never_sends_script(monkeypatch):
    sent = []
    real_get = requests.Session.get

    def spy(self, url, params=None, **kw):
        sent.append(str(params))
        return real_get(self, url, params=params, **kw)

    monkeypatch.setattr(requests.Session, "get", spy)
    with serve(make_app()) as base:
        find_reflected_xss(base, "/search", "q")
    assert sent, "the probe must use requests.Session.get"
    joined = " ".join(sent).lower()
    assert "script" not in joined and "onerror" not in joined and "alert" not in joined
