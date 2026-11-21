"""Checks exercises/devsecops/reg_probe.py: three finding probes and the red/green proof of each."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from devsecops.reg_probe import PROBES, probe_idor, probe_open_redirect, probe_path_traversal, prove_pair
from reg_fixture import PairResult, always_false, always_true
from sandpay_vuln import FLAWS, make_app, serve

pytestmark = pytest.mark.exercise

FLAW_OF = {probe_idor: "idor", probe_open_redirect: "open-redirect", probe_path_traversal: "path-traversal"}


@pytest.fixture
def dead_portal():
    """A server that answers 404 to everything: every positive control must fail against it."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

        do_POST = do_GET

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_the_probe_table_names_the_three_flaws():
    assert set(PROBES) == {"idor", "open-redirect", "path-traversal"}
    assert PROBES["idor"] is probe_idor


@pytest.mark.parametrize("probe", [probe_idor, probe_open_redirect, probe_path_traversal])
def test_each_probe_finds_its_flaw_on_the_vulnerable_portal(probe):
    with serve(make_app()) as base:
        assert probe(base) is True


@pytest.mark.parametrize("probe", [probe_idor, probe_open_redirect, probe_path_traversal])
def test_each_probe_is_quiet_once_only_its_flaw_is_fixed(probe):
    with serve(make_app({FLAW_OF[probe]})) as base:
        assert probe(base) is False


@pytest.mark.parametrize("probe", [probe_idor, probe_open_redirect, probe_path_traversal])
def test_each_probe_still_finds_its_flaw_when_every_other_flaw_is_fixed(probe):
    with serve(make_app(set(FLAWS) - {FLAW_OF[probe]})) as base:
        assert probe(base) is True


@pytest.mark.parametrize("probe", [probe_idor, probe_open_redirect, probe_path_traversal])
def test_a_failed_control_is_an_error_not_a_pass(probe, dead_portal):
    with pytest.raises(RuntimeError):
        probe(dead_portal)


def test_prove_pair_gives_red_green_for_each_real_probe():
    results = [prove_pair(flaw) for flaw in ("idor", "open-redirect", "path-traversal")]
    assert all(isinstance(r, PairResult) for r in results)
    assert [(r.flaw, r.found_on_vulnerable, r.found_on_fixed, r.verdict) for r in results] == [
        ("idor", True, False, "red-green"),
        ("open-redirect", True, False, "red-green"),
        ("path-traversal", True, False, "red-green"),
    ]


def test_prove_pair_calls_a_blind_probe_blind_and_a_noisy_one_noisy():
    blind = prove_pair("idor", always_false)
    assert (blind.found_on_vulnerable, blind.found_on_fixed, blind.verdict) == (False, False, "blind")
    noisy = prove_pair("idor", always_true)
    assert (noisy.found_on_vulnerable, noisy.found_on_fixed, noisy.verdict) == (True, True, "noisy")


def test_a_probe_that_only_fires_on_the_fixed_build_is_noisy():
    def inverted(base_url):
        return probe_idor(base_url) is False

    result = prove_pair("idor", inverted)
    assert (result.found_on_vulnerable, result.found_on_fixed, result.verdict) == (False, True, "noisy")


def test_prove_pair_refuses_a_flaw_with_no_probe():
    with pytest.raises(ValueError):
        prove_pair("sqli")
    assert prove_pair("sqli", always_false).verdict == "blind"  # a probe you pass is accepted for any flaw


def test_prove_pair_propagates_a_failed_control():
    def broken(base_url):
        raise RuntimeError("control failed")

    with pytest.raises(RuntimeError):
        prove_pair("idor", broken)
