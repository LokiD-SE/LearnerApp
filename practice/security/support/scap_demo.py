"""Prints every output the lesson security-testing-capstone shows. Run from practice/security:

    .venv/bin/python support/scap_demo.py            (uses the reference solutions)

Everything runs against the in-process practice portal on loopback; nothing leaves the machine.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "solutions"), str(ROOT / "support")]

import requests  # noqa: E402
import scap_fixture as fx  # noqa: E402
from devsecops import reg_probe, reg_registry  # noqa: E402
from sandpay_vuln import FLAWS, make_app, serve  # noqa: E402
from specialised import cvss_v4  # noqa: E402
from specialised.scap_assess import run_assessment, to_findings  # noqa: E402
from specialised.scap_retest import clean_bill, exit_code, retest  # noqa: E402
from specialised.scap_scope import GuardedHttp  # noqa: E402


def heading(text: str) -> None:
    print(f"\n=== {text}")


def assess(fixed=(), **scope_changes):
    """One assessment of a fresh portal: black-box probes through the guard, then the owner-supplied evidence."""
    app = make_app(fixed)
    with serve(app) as base:
        http = GuardedHttp(fx.make_scope(base, **scope_changes))
        black = run_assessment(http, fx.PROBES)
        white = fx.whitebox_results(app)
    return fx.Assessment(black.results + tuple(white)), http


def scope_section() -> None:
    heading("1. The guard refuses what the rules of engagement do not allow")
    with serve(make_app()) as base:
        http = GuardedHttp(fx.make_scope(base))
        host, port = base.rsplit(":", 1)[0].split("//")[1], base.rsplit(":", 1)[1]
        attempts = [
            ("GET", "/internal/admin"),
            ("GET", "/%69nternal/admin"),
            ("GET", "/public/../internal/admin"),
            ("DELETE", "/api/payments/pay_1001"),
            ("GET", "http://evil.example/health"),
            ("GET", f"http://{host}:{port}@evil.example/"),
            ("GET", "/health"),
        ]
        for method, target in attempts:
            shown = target.replace(f"{host}:{port}@", "127.0.0.1:PORT@")
            try:
                resp = http.request(method, target)
                print(f"{method:6} {shown:40} -> sent, status {resp.status_code}")
            except fx.OutOfScope as exc:
                print(f"{method:6} {shown:40} -> refused: {str(exc).replace(port, 'PORT')}")
        print(f"sent {http.used}, refused {len(http.refused)}, budget left {http.remaining}")
        loud = GuardedHttp(fx.make_scope(base, max_requests=2))
        loud.request("GET", "/health")
        loud.request("GET", "/health")
        try:
            loud.request("GET", "/health")
        except fx.BudgetExhausted as exc:
            print(f"third request with a budget of 2 -> {type(exc).__name__}: {exc}")


def assessment_section():
    heading("2. The assessment of the vulnerable portal")
    started = time.perf_counter()
    first, http = assess()
    seconds = time.perf_counter() - started
    print(f"{'flaw':16} {'status':13} {'requests':>8}")
    for r in first.results:
        print(f"{r.flaw:16} {r.status:13} {r.requests:>8}")
    black = [r for r in first.results if r.flaw in fx.BLACKBOX_FLAWS]
    print(f"black-box probes: {len(black)}, requests sent: {http.used} of a budget of {http.scope.max_requests}, "
          f"refused: {len(http.refused)}")
    print(f"found {Counter(r.status for r in first.results)['found']} of {len(first.results)}  (run took {seconds:.1f} s on this machine)")
    return first


def findings_section(first):
    heading("3. The scored findings, worst first")
    findings = to_findings(first, fx.CATALOGUE, fx.score_of)
    print(f"{'id':10} {'score':>5} {'rating':9} {'flaw':16} {'cwe':9} title")
    for f in findings:
        print(f"{f['id']:10} {f['score']:>5} {f['rating']:9} {f['flaw']:16} {f['cwe']:9} {f['title']}")
    print("by rating:", dict(Counter(f["rating"] for f in findings)))
    print("\none finding in full (evidence is what the probe recorded; nothing secret is in it):")
    print(json.dumps(findings[0], indent=2))
    ok = sum(cvss_v4.score(v) == s for v, s in fx.SCORES.items())
    print(f"\nthe pinned scores against cvss_v4.score: {ok} of {len(fx.SCORES)} distinct vectors match")
    return findings


def inconclusive_section() -> None:
    heading("4. What is NOT a clean result")
    with serve(make_app()) as base:
        http = GuardedHttp(fx.make_scope(base, max_requests=12))
        a = run_assessment(http, fx.PROBES)
        print("budget of 12:", dict(Counter(r.status for r in a.results)), f"- sent {http.used}")
        print("first not-run:", next(r.flaw for r in a.results if r.status == "not-run"))
    dead = GuardedHttp(fx.make_scope("http://127.0.0.1:1"))
    a = run_assessment(dead, fx.PROBES)
    print("nothing listening:", dict(Counter(r.status for r in a.results)), "|", a.results[0].evidence)
    print("clean bill for that run:", clean_bill(a, list(fx.BLACKBOX_FLAWS)))


def retest_section(first) -> None:
    heading("5. The retest after the developers' first round of fixes")
    round_one = {"idor", "sqli", "xss-reflected", "xss-stored", "path-traversal", "open-redirect", "jwt-none",
                 "mass-assignment", "csrf", "weak-session", "data-exposure", "verbose-errors", "weak-hash"}
    second, http = assess(round_one)
    out = retest(first, second)
    print(f"{'flaw':16} {'outcome':12} note")
    for o in out:
        print(f"{o.flaw:16} {o.outcome:12} {o.note}")
    print("outcomes:", dict(Counter(o.outcome for o in out)), "-> exit code", exit_code(out))
    print("clean bill:", clean_bill(second, [r.flaw for r in first.results]))

    heading("6. The second retest, after everything is fixed")
    third, http = assess(FLAWS)
    out = retest(first, third)
    print("outcomes:", dict(Counter(o.outcome for o in out)), "-> exit code", exit_code(out))
    print("clean bill for all 17:", clean_bill(third, [r.flaw for r in first.results]))
    print(f"requests sent: {http.used}")

    heading("7. A retest that could not run the same test")
    partial = fx.Assessment(tuple(r for r in third.results if r.flaw != "csrf"))
    out = retest(first, partial)
    print("csrf ->", [o.outcome for o in out if o.flaw == "csrf"][0], "| exit code", exit_code(out),
          "| clean bill:", clean_bill(partial, [r.flaw for r in first.results]))


def handoff_section(findings) -> None:
    heading("8. Hand-over to the regression registry")
    guards = {  # the three flaws the regression lesson wrote probes for
        "idor": "tests/regression/test_scap_idor.py::test_alice_cannot_read_bobs_payment",
        "open-redirect": "tests/regression/test_scap_redirect.py::test_login_next_stays_on_site",
        "path-traversal": "tests/regression/test_scap_files.py::test_files_stay_in_public",
    }
    entries = [
        {"id": f["id"], "flaw": f["flaw"], "severity": f["rating"], "status": "fixed", "fixed_in": "retest-2",
         "test": guards.get(f["flaw"])}
        for f in findings
    ]
    parsed = reg_registry.parse_registry(json.dumps(entries))
    test_ids = set(guards.values())
    problems = reg_registry.registry_problems(parsed, test_ids, "2026-11-21")
    print(f"{len(parsed)} fixed findings; registry problems by kind:", dict(Counter(p.kind for p in problems)))
    print("coverage:", reg_registry.coverage(parsed, test_ids))
    print("\nthe red/green pair for the three flaws that already have a probe:")
    for flaw in guards:
        pair = reg_probe.prove_pair(flaw)
        print(f"{flaw:15} found on vulnerable: {pair.found_on_vulnerable}, found on fixed: {pair.found_on_fixed}, verdict {pair.verdict}")


def main() -> None:
    print("Run date: 21 November 2026; Python", sys.version.split()[0], "requests", requests.__version__)
    scope_section()
    first = assessment_section()
    findings = findings_section(first)
    inconclusive_section()
    retest_section(first)
    handoff_section(findings)


if __name__ == "__main__":
    main()
