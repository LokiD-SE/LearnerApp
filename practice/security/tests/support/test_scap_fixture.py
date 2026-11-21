"""Checks the shared capstone helpers (support/scap_fixture.py): the scope rule, every probe on both builds, the
catalogue and the white-box checks. Not a learner exercise: it passes against both folders."""

import pytest
import requests
from sandpay_vuln import FLAWS, make_app, serve
from scap_fixture import (
    BLACKBOX_FLAWS,
    CATALOGUE,
    PROBES,
    SCORES,
    WHITEBOX_FLAWS,
    BareHttp,
    BudgetExhausted,
    Context,
    OutOfScope,
    check_scope,
    make_scope,
    rating,
    score_of,
    whitebox_results,
)
from wstg_fixture import FLAW_MAP

BASE = "http://127.0.0.1:8765"
SCOPE = make_scope(BASE)


@pytest.mark.parametrize("method, url", [
    ("GET", BASE + "/api/me"),
    ("POST", BASE + "/api/login"),
    ("PATCH", BASE + "/api/profile"),
    ("GET", BASE + "/files?name=../internal/settlement-keys.txt"),  # the query is the probe's business, not the path's
])
def test_in_scope_requests_are_allowed(method, url):
    assert check_scope(SCOPE, method, url) is None


@pytest.mark.parametrize("method, url, word", [
    ("GET", "http://127.0.0.1:9/x", "target"),
    ("GET", "http://localhost:8765/x", "target"),
    ("GET", "http://example.com/x", "loopback"),
    ("GET", "https://127.0.0.1:8765/x", "scheme"),
    ("GET", "http://127.0.0.1:8765@evil.example/", "user info"),
    ("PUT", BASE + "/x", "PUT"),
    ("GET", BASE + "/internal/admin", "excluded"),
    ("GET", BASE + "/%2e%2e/internal/admin", "excluded"),
    ("GET", BASE + "/api/../internal/admin", "excluded"),
])
def test_out_of_scope_requests_give_a_reason(method, url, word):
    reason = check_scope(SCOPE, method, url)
    assert reason is not None and word in reason


def test_rating_scale():
    assert [rating(s) for s in (0.0, 0.1, 3.9, 4.0, 6.9, 7.0, 8.9, 9.0, 10.0)] == [
        "None", "Low", "Low", "Medium", "Medium", "High", "High", "Critical", "Critical"]


def run_all(app_flaws_fixed):
    """Every probe once against a fresh portal; returns {flaw: evidence or None} and the number of requests."""
    with serve(make_app(app_flaws_fixed)) as base:
        http = BareHttp(make_scope(base))
        ctx = Context(http)
        return {flaw: probe(ctx) for flaw, probe in PROBES.items()}, http.used


def test_every_probe_finds_its_flaw_on_the_vulnerable_portal_with_evidence():
    found, used = run_all(())
    assert all(isinstance(v, str) and v for v in found.values())
    assert used < SCOPE.max_requests


def test_no_probe_reports_anything_on_the_fully_fixed_portal():
    found, _ = run_all(FLAWS)
    assert found == {flaw: None for flaw in PROBES}


@pytest.mark.parametrize("flaw", BLACKBOX_FLAWS)
def test_each_probe_goes_quiet_when_only_its_flaw_is_fixed(flaw):
    found, _ = run_all({flaw})
    assert found[flaw] is None
    assert all(found[other] for other in PROBES if other != flaw)


def test_evidence_never_carries_a_secret_value_or_a_long_digit_run():
    found, _ = run_all(())
    text = "\n".join(found.values())
    for secret in ("sk_test_", "sk_practice", "SETTLEMENT_SIGNING_KEY=", "alice-pass-1", "XX00 SAND", "sandpay-practice-only"):
        assert secret not in text
    import re

    assert not re.search(r"\d{13,19}", text)


def test_probes_send_only_harmless_requests():
    with serve(make_app()) as base:
        http = BareHttp(make_scope(base))
        for probe in PROBES.values():
            probe(Context(http))
        paths = {(e.method, e.path) for e in http.log}
    assert all(not path.startswith("/internal/") for _, path in paths)
    assert {m for m, _ in paths} <= {"GET", "POST", "PATCH"}


def test_the_login_limit_is_not_burned_by_logging_in_again_for_every_probe():
    with serve(make_app(FLAWS)) as base:
        http = BareHttp(make_scope(base))
        ctx = Context(http)
        for _ in range(10):
            ctx.login("alice")
        assert [e.path for e in http.log].count("/api/login") == 1


def test_a_failed_control_raises_control_failed():
    from scap_fixture import ControlFailed

    class Broken:
        """A context whose every GET answers 404, so every control fails."""

        def get(self, path, as_=None, **kw):
            return type("R", (), {"status_code": 404, "text": "", "headers": {}, "json": lambda self: {}})()

    with pytest.raises(ControlFailed):
        PROBES["idor"](Broken())


def test_bare_http_counts_and_has_a_budget_and_exclusions():
    with serve(make_app()) as base:
        http = BareHttp(make_scope(base), limit=2, blocked=("/internal/",))
        http.request("GET", "/health")
        with pytest.raises(OutOfScope):
            http.request("GET", "/internal/admin")
        http.request("GET", "/health")
        with pytest.raises(BudgetExhausted):
            http.request("GET", "/health")
        assert http.used == 2


def test_the_two_white_box_flaws_are_found_and_cleared():
    app = make_app()
    with serve(app) as base:
        ctx = Context(BareHttp(make_scope(base)))
        ctx.login("alice")  # a login writes the password into the log of the vulnerable portal
    weak, logging_ = whitebox_results(app)
    assert (weak.flaw, weak.status, logging_.flaw, logging_.status) == ("weak-hash", "found", "secret-logging", "found")
    fixed = make_app({"weak-hash", "secret-logging"})
    with serve(fixed) as base:
        Context(BareHttp(make_scope(base))).login("alice")
    assert [r.status for r in whitebox_results(fixed)] == ["not-found", "not-found"]


def test_black_box_and_white_box_together_cover_every_flaw():
    assert sorted(BLACKBOX_FLAWS + WHITEBOX_FLAWS) == sorted(FLAWS)


def test_the_catalogue_covers_every_flaw_and_every_vector_has_a_pinned_score():
    assert sorted(CATALOGUE) == sorted(FLAWS)
    for flaw, entry in CATALOGUE.items():
        assert entry["cwe"].startswith("CWE-") and entry["title"], flaw
        assert entry["vector"].startswith("CVSS:4.0/"), flaw
        assert 0.0 < score_of(entry["vector"]) <= 10.0, flaw
    assert set(SCORES) == {e["vector"] for e in CATALOGUE.values()}


def test_score_of_refuses_a_vector_it_was_not_given():
    with pytest.raises(ValueError):
        score_of("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:N/SA:N")


def test_every_flaw_has_wstg_and_asvs_references_in_the_flaw_map():
    assert set(FLAWS) <= set(FLAW_MAP)
