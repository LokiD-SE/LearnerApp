import pytest
from foundations.wstg_plan import PlanItem, asvs_ref, build_plan, for_level, parse_asvs_ref
from sandpay_vuln import FLAWS
from wstg_fixture import ASVS_500_SAMPLE, FLAW_MAP

pytestmark = pytest.mark.exercise


@pytest.mark.parametrize("raw, ref", [("V8.2.2", "v5.0.0-8.2.2"), ("8.2.2", "v5.0.0-8.2.2"),
                                      ("V16.5.1", "v5.0.0-16.5.1"), (" V1.2.4 ", "v5.0.0-1.2.4")])
def test_asvs_ref(raw, ref):
    assert asvs_ref(raw) == ref


def test_asvs_ref_other_version_and_errors():
    assert asvs_ref("V1.2.5", "4.0.3") == "v4.0.3-1.2.5"
    for bad in ["V8.2", "8.2.2.1", "ASVS-8.2.2", ""]:
        with pytest.raises(ValueError):
            asvs_ref(bad)
    with pytest.raises(ValueError):
        asvs_ref("V8.2.2", "5.0")


def test_parse_asvs_ref():
    assert parse_asvs_ref("v5.0.0-1.2.5") == ("5.0.0", 1, 2, 5)
    assert parse_asvs_ref("v5.0.0-16.5.1") == ("5.0.0", 16, 5, 1)
    for bad in ["V5.0.0-1.2.5", "1.2.5", "v5.0.0-V1.2.5", "v5-1.2.5"]:
        with pytest.raises(ValueError):
            parse_asvs_ref(bad)


def test_levels_are_cumulative():
    l1 = {r["req_id"] for r in for_level(ASVS_500_SAMPLE, 1)}
    l2 = {r["req_id"] for r in for_level(ASVS_500_SAMPLE, 2)}
    l3 = {r["req_id"] for r in for_level(ASVS_500_SAMPLE, 3)}
    assert l1 < l2 < l3 and len(l3) == len(ASVS_500_SAMPLE)
    assert "V8.2.2" in l1 and "V16.5.1" not in l1 and "V16.5.1" in l2 and "V13.4.6" not in l2
    with pytest.raises(ValueError):
        for_level(ASVS_500_SAMPLE, 0)


def test_plan_at_level_1():
    plan = build_plan(["idor", "verbose-errors", "missing-headers"], FLAW_MAP, ASVS_500_SAMPLE, 1)
    assert plan == [
        PlanItem("idor", ("WSTG-ATHZ-04",), ("v5.0.0-8.2.2",), ()),
        PlanItem("verbose-errors", ("WSTG-ERRH-01",), (), ("v5.0.0-16.5.1",)),
        PlanItem("missing-headers", ("WSTG-INFO-02",), (),
                 ("v5.0.0-3.4.3", "v5.0.0-3.4.4", "v5.0.0-13.4.6")),
    ]


def test_plan_at_level_2_and_gaps():
    plan = {p.flaw: p for p in build_plan(list(FLAWS), FLAW_MAP, ASVS_500_SAMPLE, 2)}
    assert plan["missing-headers"].asvs == ("v5.0.0-3.4.3", "v5.0.0-3.4.4")
    assert plan["missing-headers"].deferred == ("v5.0.0-13.4.6",)
    assert sorted(f for f, p in plan.items() if p.wstg_gap) == ["data-exposure", "jwt-none", "secret-logging"]
    assert not plan["idor"].wstg_gap


def test_plan_keeps_the_given_order():
    flaws = ["sqli", "idor", "csrf"]
    assert [p.flaw for p in build_plan(flaws, FLAW_MAP, ASVS_500_SAMPLE, 3)] == flaws


def test_plan_never_drops_a_risk_silently():
    with pytest.raises(KeyError):
        build_plan(["clickjacking"], FLAW_MAP, ASVS_500_SAMPLE, 1)
    broken = {"idor": {"wstg": ["WSTG-ATHZ-04"], "asvs": ["V99.1.1"]}}
    with pytest.raises(KeyError):
        build_plan(["idor"], broken, ASVS_500_SAMPLE, 1)
