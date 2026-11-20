import pytest
import requests
from api.apitop_probe import Finding, probe_api
from apitop_fixture import tokens
from sandpay_vuln import make_app, serve

pytestmark = pytest.mark.exercise

# the flaws probe_api can see; weak-hash is left unfixed here because fixing it makes every sign-in slow
COVERED = {"idor", "jwt-none", "no-rate-limit", "mass-assignment", "data-exposure", "ssrf", "verbose-errors",
           "missing-headers"}
RISK_OF = {"idor": "API1:2023", "jwt-none": "API2:2023", "no-rate-limit": "API4:2023",
           "mass-assignment": "API3:2023", "data-exposure": "API3:2023", "ssrf": "API7:2023",
           "verbose-errors": "API8:2023", "missing-headers": "API8:2023"}


def run(fixed):
    with serve(make_app(fixed)) as base:
        t = tokens(base)
        return probe_api(base, t["alice"], t["bob"])


def test_finds_all_eight_flaws_on_the_vulnerable_portal():
    findings = run(set())
    assert all(isinstance(f, Finding) for f in findings)
    assert sorted(f.flaw for f in findings) == sorted(COVERED)
    assert {f.flaw: f.risk for f in findings} == RISK_OF
    assert [f.risk for f in findings] == sorted((f.risk for f in findings), key=lambda r: int(r[3:].split(":")[0]))


def test_reports_nothing_once_every_covered_flaw_is_fixed():
    assert run(COVERED) == []


@pytest.mark.parametrize("flaw", sorted(COVERED))
def test_each_check_sees_only_its_own_flaw(flaw):
    # everything fixed except one flaw: exactly that finding, and the evidence is a non-empty line
    findings = run(COVERED - {flaw})
    assert [f.flaw for f in findings] == [flaw]
    assert findings[0].risk == RISK_OF[flaw]
    assert findings[0].evidence


def test_evidence_never_contains_a_secret_value():
    with serve(make_app()) as base:
        t = tokens(base)
        text = " ".join(f.evidence for f in probe_api(base, t["alice"], t["bob"]))
    assert "sk_test_shop" not in text and "XX00 SAND" not in text


def test_the_property_probe_changes_nothing():
    with serve(make_app()) as base:
        t = tokens(base)
        before = requests.get(base + "/api/me", headers={"Authorization": f"Bearer {t['alice']}"}, timeout=5).json()
        probe_api(base, t["alice"], t["bob"])
        after = requests.get(base + "/api/me", headers={"Authorization": f"Bearer {t['alice']}"}, timeout=5).json()
    assert before == after


def test_a_failed_control_stops_the_probe():
    with serve(make_app()) as base:
        t = tokens(base)
        with pytest.raises(RuntimeError):
            probe_api(base, "not-a-token", t["bob"])
