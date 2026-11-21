"""Checks exercises/api/mass_probe.py against the loopback portal, with and without the flaw."""

import pytest
import requests
from api.mass_probe import MassAssignmentResult, probe_mass_assignment, read_profile
from apitop_fixture import tokens
from sandpay_vuln import make_app, serve

pytestmark = pytest.mark.exercise


def run(fixed, who="alice"):
    with serve(make_app(fixed)) as base:
        token = tokens(base)[who]
        before = read_profile(base, token)
        result = probe_mass_assignment(base, token)
        return result, before, read_profile(base, token)


def test_finds_both_privileged_fields_on_the_vulnerable_portal():
    result, _, _ = run(set())
    assert isinstance(result, MassAssignmentResult)
    assert result.vulnerable is True
    assert result.control_ok is True
    assert sorted(result.accepted) == ["merchant_id", "role"]
    assert "role" in result.evidence


def test_reports_nothing_once_mass_assignment_is_fixed():
    result, _, _ = run({"mass-assignment"})
    assert result.vulnerable is False
    assert result.accepted == []
    assert result.control_ok is True
    assert result.refused == {"role": 400, "merchant_id": 400}


def test_the_probe_changes_nothing():
    for fixed in (set(), {"mass-assignment"}):
        _, before, after = run(fixed)
        assert before == after


def test_works_for_another_account():
    result, _, _ = run(set(), who="bob")
    assert result.vulnerable is True


def test_refuses_a_verdict_when_the_token_does_not_work():
    with serve(make_app()) as base:
        with pytest.raises(RuntimeError):
            probe_mass_assignment(base, "not-a-token")


def test_refuses_a_verdict_when_the_control_patch_fails():
    # ops has no merchant, but display_name is still editable, so break the control another way: an unknown
    # server that answers 405 to PATCH
    import http.server
    import threading

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = b'{"email": "a@b.example", "merchant_id": "m", "role": "r", "display_name": "d"}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_PATCH(self):
            self.send_response(405)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *a):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with pytest.raises(RuntimeError):
            probe_mass_assignment(f"http://127.0.0.1:{server.server_port}", "x")
    finally:
        server.shutdown()
        server.server_close()
