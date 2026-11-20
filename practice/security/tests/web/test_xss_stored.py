import re

import pytest
import requests
from sandpay_vuln import make_app, serve
from web.xss_stored import make_marker, probe_stored

pytestmark = pytest.mark.exercise


def login(base, email="alice@shop-a.example", password="alice-pass-1"):
    r = requests.post(base + "/api/login", json={"email": email, "password": password}, timeout=5)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_marker_is_harmless_and_unique():
    canary, payload = make_marker()
    assert make_marker()[0] != canary
    assert canary in payload and payload.startswith("<")
    lowered = payload.lower()
    for forbidden in ("script", "on", "javascript:", "src=", "href=", "style"):
        assert forbidden not in lowered.replace(canary, ""), forbidden
    assert re.fullmatch(r"[a-z0-9]{8,}", canary)


def test_finds_stored_xss_in_notes():
    with serve(make_app()) as base:
        finding = probe_stored(base, login(base))
    assert finding is not None
    assert finding.write_path == "/api/notes" and finding.read_path == "/notes"
    assert finding.payload in finding.evidence and "<li>" in finding.evidence


def test_quiet_when_fixed():
    with serve(make_app({"xss-stored"})) as base:
        assert probe_stored(base, login(base)) is None


def test_finds_only_its_own_marker():
    # An earlier, encoded note from someone else must not be confused with this probe's marker.
    with serve(make_app({"xss-stored"})) as base:
        token = login(base)
        requests.post(base + "/api/notes", json={"body": "<b>old note</b>"}, headers={"Authorization": f"Bearer {token}"}, timeout=5)
        assert probe_stored(base, token) is None


def test_refuses_to_conclude_when_the_write_fails():
    with serve(make_app()) as base:
        with pytest.raises(RuntimeError, match="write failed"):
            probe_stored(base, "not-a-token")


def test_refuses_to_conclude_when_the_marker_is_not_displayed():
    with serve(make_app()) as base:
        with pytest.raises(RuntimeError, match="nothing proved"):
            probe_stored(base, login(base), read_path="/settings")
