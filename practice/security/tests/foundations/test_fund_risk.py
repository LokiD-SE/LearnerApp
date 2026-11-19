import pytest
from foundations.fund_risk import OPTIONS, impact, level, likelihood, rate

pytestmark = pytest.mark.exercise

# The worked example from the OWASP Risk Rating Methodology ("Repeatable Method").
EXAMPLE = {
    "skill_level": 5, "motive": 2, "opportunity": 7, "size": 1,
    "ease_of_discovery": 3, "ease_of_exploit": 6, "awareness": 9, "intrusion_detection": 2,
    "loss_of_confidentiality": 9, "loss_of_integrity": 7, "loss_of_availability": 5, "loss_of_accountability": 8,
    "financial_damage": 1, "reputation_damage": 2, "non_compliance": 1, "privacy_violation": 5,
}
TECHNICAL_ONLY = {k: v for k, v in EXAMPLE.items() if k not in
                  ("financial_damage", "reputation_damage", "non_compliance", "privacy_violation")}


def test_the_methodologys_worked_example():
    assert likelihood(EXAMPLE) == pytest.approx(4.375)
    assert impact(EXAMPLE, "technical") == pytest.approx(7.25)
    assert impact(EXAMPLE, "business") == pytest.approx(2.25)
    r = rate(EXAMPLE)
    assert (r.likelihood_level, r.impact_basis, r.impact_level, r.severity) == ("MEDIUM", "business", "LOW", "Low")


def test_without_business_information_technical_impact_is_used():
    r = rate(TECHNICAL_ONLY)
    assert (r.impact_basis, r.impact_level, r.severity) == ("technical", "HIGH", "High")


@pytest.mark.parametrize("score,expected", [(0, "LOW"), (2.99, "LOW"), (3, "MEDIUM"), (5.99, "MEDIUM"),
                                            (6, "HIGH"), (9, "HIGH")])
def test_level_boundaries(score, expected):
    assert level(score) == expected


@pytest.mark.parametrize("lk,im,sev", [(0, 0, "Note"), (8, 0, "Medium"), (0, 8, "Medium"), (4, 4, "Medium"),
                                       (8, 8, "Critical"), (4, 8, "High"), (8, 4, "High"), (0, 4, "Low")])
def test_severity_table(lk, im, sev):
    scores = {k: lk for k in TECHNICAL_ONLY if not k.startswith("loss_")}
    scores |= {k: im for k in TECHNICAL_ONLY if k.startswith("loss_")}
    assert rate(scores).severity == sev


def test_strict_mode_rejects_values_that_are_not_options():
    with pytest.raises(ValueError, match="motive"):
        rate(EXAMPLE, strict=True)
    listed = {k: max(OPTIONS[k]) for k in TECHNICAL_ONLY}
    assert rate(listed, strict=True).severity == "Critical"


@pytest.mark.parametrize("bad", [10, -1, 4.5, "7", True])
def test_rejects_values_outside_the_scale(bad):
    with pytest.raises(ValueError):
        likelihood({**EXAMPLE, "awareness": bad})


def test_rejects_missing_factors():
    with pytest.raises(ValueError, match="missing"):
        likelihood({"skill_level": 5})
    with pytest.raises(ValueError):
        impact(EXAMPLE, "financial")
