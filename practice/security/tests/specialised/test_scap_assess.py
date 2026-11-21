"""Checks exercises/specialised/scap_assess.py: run the probes, give each a verdict, and build scored findings.

The tests use ``BareHttp`` from the fixture (no rules, only counting), so they do not depend on ``GuardedHttp``.
"""

import pytest
import requests
from sandpay_vuln import FLAWS, make_app, serve
from scap_fixture import (
    BLACKBOX_FLAWS,
    CATALOGUE,
    PROBES,
    Assessment,
    BareHttp,
    BudgetExhausted,
    ControlFailed,
    OutOfScope,
    Result,
    make_scope,
    score_of,
)
from specialised.scap_assess import run_assessment, to_findings

pytestmark = pytest.mark.exercise


def assess(fixed=(), **bare):
    with serve(make_app(fixed)) as base:
        http = BareHttp(make_scope(base), **bare)
        return run_assessment(http, PROBES), http


# ---- verdicts, with probes that never touch the network ---------------------------------------------------------


class FakeHttp:
    scope = None

    def __init__(self):
        self.used = 0


def fake(*steps):
    """Probes built from simple behaviours: a string is evidence, None is 'not seen', an exception is raised."""
    probes = {}
    for i, step in enumerate(steps):
        def probe(ctx, step=step):
            ctx.http.used += 1
            if isinstance(step, BaseException):
                raise step
            return step
        probes[f"flaw-{i}"] = probe
    return probes


def test_evidence_means_found_and_none_means_not_found():
    a = run_assessment(FakeHttp(), fake("it leaks", None))
    assert [(r.flaw, r.status) for r in a.results] == [("flaw-0", "found"), ("flaw-1", "not-found")]
    assert a.results[0].evidence == "it leaks"
    assert a.results[1].evidence  # says why, so a reader knows the control worked


def test_a_failed_control_is_inconclusive_never_not_found():
    a = run_assessment(FakeHttp(), fake(ControlFailed("control failed: login answered 500")))
    assert a.results[0].status == "inconclusive"
    assert a.results[0].evidence == "control failed: login answered 500"


def test_transport_errors_and_crashes_are_inconclusive_with_the_reason():
    a = run_assessment(FakeHttp(), fake(requests.ConnectionError("down"), ValueError("boom")))
    assert [r.status for r in a.results] == ["inconclusive", "inconclusive"]
    assert a.results[0].evidence == "transport error: ConnectionError"
    assert a.results[1].evidence == "probe crashed: ValueError: boom"


def test_a_crashed_probe_does_not_stop_the_run():
    a = run_assessment(FakeHttp(), fake(ValueError("boom"), "later flaw is still found"))
    assert [r.status for r in a.results] == ["inconclusive", "found"]


def test_out_of_scope_is_blocked_and_the_run_continues():
    a = run_assessment(FakeHttp(), fake(OutOfScope("path /internal/ is excluded"), "found after"))
    assert a.results[0].status == "blocked"
    assert a.results[0].evidence == "refused by the rules of engagement: path /internal/ is excluded"
    assert a.results[1].status == "found"


def test_budget_exhaustion_stops_the_run_and_marks_the_rest_not_run():
    called = []
    probes = fake("a", BudgetExhausted("used up"), "c", "d")
    probes["flaw-2"] = lambda ctx: called.append("c")
    probes["flaw-3"] = lambda ctx: called.append("d")
    a = run_assessment(FakeHttp(), probes)
    assert [r.status for r in a.results] == ["found", "not-run", "not-run", "not-run"]
    assert [r.flaw for r in a.results] == ["flaw-0", "flaw-1", "flaw-2", "flaw-3"]
    assert called == []
    assert all(r.requests == 0 for r in a.results[1:])


def test_requests_counts_what_each_probe_sent():
    def three(ctx):
        ctx.http.used += 3

    def one(ctx):
        ctx.http.used += 1

    a = run_assessment(FakeHttp(), {"a": three, "b": one, "c": lambda ctx: None})
    assert [r.requests for r in a.results] == [3, 1, 0]


def test_every_probe_shares_one_context():
    seen = []
    run_assessment(FakeHttp(), {"a": lambda ctx: seen.append(ctx), "b": lambda ctx: seen.append(ctx)})
    assert len(seen) == 2 and seen[0] is seen[1]


def test_results_keep_the_order_of_the_probes():
    a = run_assessment(FakeHttp(), fake(None, "x", None))
    assert [r.flaw for r in a.results] == ["flaw-0", "flaw-1", "flaw-2"]


# ---- the real probes against the practice portal --------------------------------------------------------------------


def test_the_vulnerable_portal_shows_every_flaw_the_probes_cover():
    a, http = assess()
    assert sorted(a.found()) == sorted(BLACKBOX_FLAWS)
    assert sum(r.requests for r in a.results) == http.used


def test_the_fully_fixed_portal_comes_back_clean_with_every_control_working():
    a, _ = assess(FLAWS)
    assert [r.status for r in a.results] == ["not-found"] * len(BLACKBOX_FLAWS)


@pytest.mark.parametrize("flaw", BLACKBOX_FLAWS)
def test_fixing_one_flaw_clears_that_probe_and_only_that_probe(flaw):
    a, _ = assess({flaw})
    assert a.get(flaw).status == "not-found"
    assert sorted(a.found()) == sorted(set(BLACKBOX_FLAWS) - {flaw})


def test_a_budget_that_runs_out_midway_leaves_a_clear_trail():
    a, http = assess(limit=10)
    statuses = [r.status for r in a.results]
    first = statuses.index("not-run")
    assert set(statuses[first:]) == {"not-run"}
    assert set(statuses[:first]) <= {"found", "not-found", "inconclusive"}
    assert http.used == 10


def test_a_portal_that_is_down_gives_inconclusive_not_not_found():
    scope = make_scope("http://127.0.0.1:1")  # nothing listens there
    a = run_assessment(BareHttp(scope), PROBES)
    assert {r.status for r in a.results} == {"inconclusive"}
    assert all(r.evidence.startswith("transport error") for r in a.results)


# ---- findings ------------------------------------------------------------------------------------------------------


def hand_made():
    return Assessment((
        Result("sqli", "found", "tautology returned rows of m_200"),
        Result("jwt-none", "found", "an unsigned token was accepted"),
        Result("xss-stored", "inconclusive", "control failed"),
        Result("idor", "found", "alice read pay_2001"),
        Result("csrf", "not-found", "clear"),
    ))


def test_findings_are_the_found_results_worst_first_with_ties_broken_by_flaw_id():
    findings = to_findings(hand_made(), CATALOGUE, score_of)
    assert [f["flaw"] for f in findings] == ["jwt-none", "idor", "sqli"]  # 9.3, then 7.1 and 7.1 by name
    assert [f["id"] for f in findings] == ["SP-CAP-01", "SP-CAP-02", "SP-CAP-03"]


def test_a_finding_carries_everything_the_report_needs():
    top = to_findings(hand_made(), CATALOGUE, score_of)[0]
    assert top["title"] == CATALOGUE["jwt-none"]["title"]
    assert top["cwe"] == "CWE-347"
    assert top["vector"] == CATALOGUE["jwt-none"]["vector"]
    assert top["score"] == 9.3 and top["rating"] == "Critical"
    assert top["evidence"] == "an unsigned token was accepted"
    assert top["refs"] == {"wstg": [], "asvs": ["V9.1.1", "V9.1.2"]}


def test_wstg_and_asvs_references_come_from_the_flaw_map_and_are_copies():
    idor = [f for f in to_findings(hand_made(), CATALOGUE, score_of) if f["flaw"] == "idor"][0]
    assert idor["refs"] == {"wstg": ["WSTG-ATHZ-04"], "asvs": ["V8.2.2"]}
    idor["refs"]["wstg"].append("changed")
    again = [f for f in to_findings(hand_made(), CATALOGUE, score_of) if f["flaw"] == "idor"][0]
    assert again["refs"]["wstg"] == ["WSTG-ATHZ-04"]


def test_the_score_comes_from_the_function_you_pass_in():
    findings = to_findings(hand_made(), CATALOGUE, lambda vector: 1.0)
    assert {f["score"] for f in findings} == {1.0}
    assert {f["rating"] for f in findings} == {"Low"}


def test_no_found_result_means_no_findings():
    clean = Assessment((Result("idor", "not-found", "clear"), Result("sqli", "blocked", "refused")))
    assert to_findings(clean, CATALOGUE, score_of) == []


def test_a_found_flaw_with_no_catalogue_entry_is_loud():
    odd = Assessment((Result("made-up-flaw", "found", "x"),))
    with pytest.raises(KeyError):
        to_findings(odd, CATALOGUE, score_of)


def test_a_full_assessment_becomes_fifteen_findings_with_unique_ids():
    a, _ = assess()
    findings = to_findings(a, CATALOGUE, score_of)
    assert len(findings) == 15
    assert len({f["id"] for f in findings}) == 15
    scores = [f["score"] for f in findings]
    assert scores == sorted(scores, reverse=True)
    assert findings[0]["flaw"] == "jwt-none"
