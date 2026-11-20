import json

import pytest
import requests
from sandpay_vuln import FLAWS, make_app, serve
from ssrf_fixture import CallbackListener, alice_token, listening
from web.ssrf_probe import Finding, classify, portal_webhook_sender, probe_blind, probe_ssrf

pytestmark = pytest.mark.exercise

ADMIN_BODY = json.dumps({"admin": True, "settlement_key": "sk_practice_do_not_use"})
INTERNAL = "http://127.0.0.1:9/internal/admin"


def answer(delivered, preview=""):
    return 200, json.dumps({"delivered": delivered, "status": 200, "response_preview": preview})


# ---- classify ---------------------------------------------------------------------------------------------
def test_classify_a_fetch():
    assert classify(*answer(True, "hello")) == "fetched"


def test_classify_a_200_that_did_not_fetch():
    assert classify(*answer(False)) == "not-fetched"
    assert classify(200, "<html>ok</html>") == "not-fetched"
    assert classify(200, json.dumps(["delivered"])) == "not-fetched"


def test_classify_refusals_and_failures():
    assert classify(400, json.dumps({"error": "webhook url must be a public address"})) == "rejected"
    assert classify(403, "") == "rejected"
    assert classify(500, "Traceback (most recent call last): ...") == "unreachable"
    assert classify(502, "") == "unreachable"


def test_delivered_must_be_exactly_true():
    assert classify(200, json.dumps({"delivered": "yes"})) == "not-fetched"


# ---- in-band probe against fakes ---------------------------------------------------------------------
def test_flags_a_server_that_returns_the_internal_page():
    finding = probe_ssrf(lambda url: answer(True, ADMIN_BODY), INTERNAL, "settlement_key")
    assert isinstance(finding, Finding)
    assert (finding.technique, finding.url) == ("in-band", INTERNAL)
    assert "settlement_key" in finding.evidence


def test_quiet_when_the_server_refuses_the_url():
    refuse = lambda url: (400, json.dumps({"error": "webhook url must be a public address"}))  # noqa: E731
    assert probe_ssrf(refuse, INTERNAL, "settlement_key") is None


def test_quiet_when_the_server_only_acknowledges():
    assert probe_ssrf(lambda url: answer(False), INTERNAL, "settlement_key") is None


def test_an_echo_of_the_url_is_not_proof():
    # An error that merely repeats the request must not count: the marker has to come from the internal page.
    echo = lambda url: (500, json.dumps({"error": f"could not fetch {url} (settlement_key)"}))  # noqa: E731
    assert probe_ssrf(echo, INTERNAL, "settlement_key") is None


def test_a_fetch_without_the_marker_is_not_a_finding():
    assert probe_ssrf(lambda url: answer(True, "<html>public page</html>"), INTERNAL, "settlement_key") is None


# ---- blind probe against a real listener -------------------------------------------------------------
def fetch_for_real(url):
    """A target that fetches whatever it is given and tells the caller nothing."""
    requests.get(url, timeout=2)
    return 202, ""


def test_blind_finds_a_server_that_calls_back():
    with listening() as listener:
        finding = probe_blind(fetch_for_real, listener)
        assert finding is not None and finding.technique == "blind"
        assert finding.url.startswith(listener.url(""))
        assert listener.hits and listener.hits[0][0].startswith("/cb/")


def test_blind_is_quiet_when_the_server_never_calls():
    with listening() as listener:
        assert probe_blind(lambda url: (202, ""), listener) is None
        assert listener.hits == []


def test_blind_ignores_a_hit_that_belongs_to_another_token():
    with listening() as listener:
        listener.hits.append(("/cb/someone-else", "x"))
        assert probe_blind(lambda url: (202, ""), listener) is None


def test_the_listener_only_binds_to_loopback():
    with pytest.raises(ValueError):
        CallbackListener(host="0.0.0.0")


# ---- against the practice portal ------------------------------------------------------------------------
def portal(app, fn):
    with serve(app) as base:
        return fn(base, portal_webhook_sender(base, alice_token(base)))


def test_finds_the_flaw_in_band():
    f = portal(make_app(), lambda base, send: probe_ssrf(send, f"{base}/internal/admin", "settlement_key"))
    assert f is not None and f.technique == "in-band"


def test_quiet_in_band_once_ssrf_is_fixed():
    assert portal(make_app({"ssrf"}), lambda base, send: probe_ssrf(send, f"{base}/internal/admin", "settlement_key")) is None


def test_finds_the_flaw_blind_with_a_listener():
    with listening() as listener:
        f = portal(make_app(), lambda base, send: probe_blind(send, listener))
        assert f is not None and "the listener received" in f.evidence
        assert "Python-urllib" in listener.hits[0][1]  # the fetch came from the portal's urllib, not from us


def test_quiet_blind_once_ssrf_is_fixed():
    with listening() as listener:
        assert portal(make_app({"ssrf"}), lambda base, send: probe_blind(send, listener)) is None
        assert listener.hits == []


def test_quiet_on_the_fully_fixed_portal():
    with listening() as listener:
        assert portal(make_app(FLAWS), lambda base, send: probe_blind(send, listener)) is None
        assert portal(make_app(FLAWS), lambda base, send: probe_ssrf(send, f"{base}/internal/admin", "settlement_key")) is None
