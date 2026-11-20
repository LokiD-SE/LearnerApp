import pytest
from api.apitop_map import RISKS, group_by_risk, risks_for_flaw, untested_risks
from sandpay_vuln import FLAWS

pytestmark = pytest.mark.exercise


def test_the_ten_risks_are_listed_in_order():
    assert list(RISKS) == [f"API{n}:2023" for n in range(1, 11)]


@pytest.mark.parametrize("flaw, risks", [
    ("idor", ["API1:2023"]),
    ("mass-assignment", ["API3:2023"]),
    ("data-exposure", ["API3:2023"]),
    ("jwt-none", ["API2:2023"]),
    ("weak-hash", ["API2:2023"]),
    ("no-rate-limit", ["API4:2023", "API2:2023"]),
    ("ssrf", ["API7:2023"]),
    ("verbose-errors", ["API8:2023"]),
    ("missing-headers", ["API8:2023"]),
])
def test_flaws_that_belong_to_an_api_risk(flaw, risks):
    assert risks_for_flaw(flaw) == risks


@pytest.mark.parametrize("flaw", ["sqli", "xss-reflected", "xss-stored", "csrf", "open-redirect", "path-traversal",
                                  "weak-session", "secret-logging"])
def test_flaws_the_2023_list_has_no_category_for(flaw):
    assert risks_for_flaw(flaw) == []


def test_every_portal_flaw_is_classified_and_every_answer_is_a_listed_risk():
    for flaw in FLAWS:
        assert all(risk in RISKS for risk in risks_for_flaw(flaw))


def test_an_unknown_flaw_is_an_error_not_an_empty_answer():
    with pytest.raises(ValueError):
        risks_for_flaw("idorr")


def test_the_answer_is_a_copy_the_caller_may_change():
    first = risks_for_flaw("no-rate-limit")
    first.append("API99:2023")
    assert risks_for_flaw("no-rate-limit") == ["API4:2023", "API2:2023"]


def test_group_by_risk_orders_risks_by_number_and_flaws_by_input():
    got = group_by_risk(["ssrf", "no-rate-limit", "idor", "weak-hash", "csrf", "mass-assignment"])
    assert got == {
        "API1:2023": ["idor"],
        "API2:2023": ["no-rate-limit", "weak-hash"],
        "API3:2023": ["mass-assignment"],
        "API4:2023": ["no-rate-limit"],
        "API7:2023": ["ssrf"],
    }
    assert list(got) == ["API1:2023", "API2:2023", "API3:2023", "API4:2023", "API7:2023"]


def test_group_by_risk_of_nothing_is_empty():
    assert group_by_risk([]) == {}
    assert group_by_risk(["csrf", "sqli"]) == {}


def test_the_whole_portal_leaves_four_risks_without_any_flaw():
    # the blind spots: no seeded flaw shows function-level authorization, business flows, inventory or
    # unsafe consumption of third-party APIs - they need a design review or other tests
    assert untested_risks(list(FLAWS)) == ["API5:2023", "API6:2023", "API9:2023", "API10:2023"]


def test_untested_risks_shrinks_as_evidence_is_added():
    assert untested_risks([]) == list(RISKS)
    assert "API1:2023" not in untested_risks(["idor"])
    assert untested_risks(["idor"]) == [r for r in RISKS if r != "API1:2023"]
