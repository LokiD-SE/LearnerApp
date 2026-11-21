"""Checks exercises/devsecops/zap_replay.py: flatten a synthetic ZAP-style report, then replay its instances."""

import pytest
from devsecops.zap_replay import flatten, replay, replay_report, summarise
from sandpay_vuln import make_app, serve
from zap_fixture import Finding, sample_report

pytestmark = pytest.mark.exercise

BASE = "http://127.0.0.1:9"


def test_flatten_gives_one_finding_per_instance_in_report_order():
    findings = flatten(sample_report(BASE))
    assert [f.rule_id for f in findings] == ["40012", "6-1", "6-1", "40014", "10038-1", "10038-1"]
    assert [f.risk for f in findings] == ["High", "High", "High", "High", "Medium", "Medium"]
    assert [f.confidence for f in findings] == ["Medium", "Medium", "Medium", "Medium", "High", "High"]


def test_flatten_copies_the_instance_fields():
    xss = flatten(sample_report(BASE))[0]
    assert isinstance(xss, Finding)
    assert (xss.name, xss.method, xss.param) == ("Cross Site Scripting (Reflected)", "GET", "q")
    assert xss.attack == xss.evidence == "<script>alert(1)</script>"
    assert xss.uri.startswith(BASE + "/search?q=")
    passive = flatten(sample_report(BASE))[-1]
    assert (passive.param, passive.attack, passive.evidence) == ("", "", "")


def test_flatten_falls_back_to_plugin_id_and_maps_every_code():
    report = {"site": [{"alerts": [
        {"pluginid": "10021", "name": "X", "riskcode": "0", "confidence": "0", "instances": [{"uri": BASE + "/a"}]},
        {"pluginid": "1", "alertRef": "1-2", "name": "Y", "riskcode": "1", "confidence": "4", "instances": [{"uri": BASE + "/b"}]},
    ]}]}
    first, second = flatten(report)
    assert (first.rule_id, first.risk, first.confidence, first.method) == ("10021", "Informational", "False Positive", "GET")
    assert (second.rule_id, second.risk, second.confidence) == ("1-2", "Low", "Confirmed")


def test_flatten_of_an_empty_report():
    assert flatten({}) == []
    assert flatten({"site": [{"alerts": []}]}) == []


def outcomes(fixed):
    with serve(make_app(fixed)) as base:
        return [outcome for _, outcome in replay_report(sample_report(base))]


def test_vulnerable_portal_reproduces_the_real_alerts_and_not_the_stale_one():
    assert outcomes(set()) == [
        "reproduced", "reproduced", "not-reproduced", "not-replayable", "not-replayable", "not-replayable",
    ]


def test_fixed_portal_reproduces_nothing():
    got = outcomes({"xss-reflected", "path-traversal"})
    assert got == ["not-reproduced", "not-reproduced", "not-reproduced", "not-replayable", "not-replayable", "not-replayable"]


def test_a_matching_body_with_the_wrong_status_is_not_a_reproduction():
    with serve(make_app()) as base:
        finding = Finding("6-1", "Path Traversal", "High", base + "/files?name=zzz", param="name", attack="zzz", evidence="file not found")
        assert replay(finding) == "not-reproduced"


def test_summarise_counts_all_three_outcomes():
    with serve(make_app()) as base:
        results = replay_report(sample_report(base))
    assert summarise(results) == {"reproduced": 2, "not-reproduced": 1, "not-replayable": 3}
    assert summarise([]) == {"reproduced": 0, "not-reproduced": 0, "not-replayable": 0}


def test_post_and_passive_instances_are_not_replayable_and_send_nothing():
    post = Finding("40014", "XSS", "High", BASE + "/api/notes", "POST", "body", "<x>", "<x>")
    passive = Finding("10038-1", "CSP", "Medium", BASE + "/login")
    assert replay(post) == "not-replayable"
    assert replay(passive) == "not-replayable"


@pytest.mark.parametrize("uri", ["http://203.0.113.9/x?q=1", "https://shop.example/x", "http://127.0.0.1.evil.example/x"])
def test_refuses_to_replay_outside_loopback(uri):
    with pytest.raises(ValueError):
        replay(Finding("40012", "XSS", "High", uri, param="q", attack="a", evidence="a"))
    with pytest.raises(ValueError):
        replay(Finding("40014", "XSS", "High", uri, "POST"))
