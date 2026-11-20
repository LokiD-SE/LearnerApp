"""Exercise: read a .jmx as a tree and work out scope (exercises/jmeter/jm_arch_tree.py)."""

from pathlib import Path

import pytest
from jmeter.jm_arch_tree import classify, parse_jmx, scope

pytestmark = pytest.mark.exercise

SHOP = Path(__file__).parent / "fixtures" / "jm_arch_shop.jmx"


@pytest.mark.parametrize("testclass, kind", [
    ("TestPlan", "test-plan"), ("ThreadGroup", "thread-group"), ("SetupThreadGroup", "thread-group"),
    ("HTTPSamplerProxy", "sampler"), ("JSR223Sampler", "sampler"), ("DebugSampler", "sampler"),
    ("LoopController", "controller"), ("OnceOnlyController", "controller"), ("TransactionController", "controller"),
    ("GenericController", "controller"), ("ConfigTestElement", "config"), ("CookieManager", "config"),
    ("HeaderManager", "config"), ("CSVDataSet", "config"), ("CounterConfig", "config"), ("Arguments", "config"),
    ("JSR223PreProcessor", "pre"), ("UserParameters", "other"), ("JSONPostProcessor", "post"),
    ("RegexExtractor", "post"), ("BoundaryExtractor", "post"), ("ConstantTimer", "timer"),
    ("UniformRandomTimer", "timer"), ("ResponseAssertion", "assertion"), ("DurationAssertion", "assertion"),
    ("ResultCollector", "listener"), ("BackendListener", "listener"),
])
def test_classify(testclass, kind):
    assert classify(testclass) == kind


def test_parse_pairs_elements_with_their_hash_trees():
    plan = parse_jmx(SHOP)
    assert (plan.kind, plan.name) == ("test-plan", "SandPay shop plan")
    assert [c.name for c in plan.children] == ["Summary Report", "Merchants"]
    merchants = plan.children[1]
    assert [c.name for c in merchants.children] == [
        "HTTP Request Defaults", "Cookie Manager", "Think time", "Under 2 s (disabled)", "Sign in once",
        "GET /v1/payments", "Open three payments", "Reports (disabled)",
    ]
    assert merchants.children[3].enabled is False
    assert [c.name for c in merchants.children[4].children[0].children] == ["Extract token"]


def test_parse_rejects_broken_pairs(tmp_path):
    bad = tmp_path / "bad.jmx"
    bad.write_text(
        '<jmeterTestPlan version="1.2"><hashTree>'
        '<TestPlan testclass="TestPlan" testname="P"/><hashTree>'
        '<ThreadGroup testclass="ThreadGroup" testname="TG"/>'  # no hashTree after the thread group
        '</hashTree></hashTree></jmeterTestPlan>'
    )
    with pytest.raises(ValueError):
        parse_jmx(bad)


def test_parse_rejects_files_that_are_not_test_plans(tmp_path):
    other = tmp_path / "pom.xml"
    other.write_text("<project><hashTree/></project>")
    with pytest.raises(ValueError):
        parse_jmx(other)


def test_scope_per_sampler():
    s = scope(parse_jmx(SHOP))
    assert set(s) == {"POST /auth/token", "GET /v1/payments", "GET /v1/payments/{id}"}  # disabled branch left out
    assert s["POST /auth/token"]["post"] == ["Extract token"]
    assert s["GET /v1/payments"]["post"] == []  # the extractor is a child of the sign-in sampler only
    assert s["GET /v1/payments"]["assertion"] == ["Status is 200"]  # the disabled assertion takes no part
    assert s["GET /v1/payments/{id}"]["timer"] == ["Think time", "Read the payment"]  # after the sampler, still applies
    assert s["GET /v1/payments/{id}"]["config"] == ["HTTP Request Defaults", "Cookie Manager", "Bearer token"]
    assert "Bearer token" not in s["GET /v1/payments"]["config"]
    assert all(v["listener"] == ["Summary Report"] for v in s.values())  # a listener under the Test Plan sees all
