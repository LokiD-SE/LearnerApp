"""The OWASP Risk Rating Methodology, "Repeatable Method" (owasp.org/www-community/OWASP_Risk_Rating_Methodology).

"Risk = Likelihood * Impact". Each factor is rated 0-9; likelihood is the average of 8 factors (4 threat
agent, 4 vulnerability), impact the average of 4 technical or 4 business factors. Scores map to levels
("0 to <3" LOW, "3 to <6" MEDIUM, "6 to 9" HIGH), and a 3x3 table combines the two levels into a severity
(Note, Low, Medium, High, Critical). The methodology says to use business impact when you have good business
information and technical impact otherwise.

``OPTIONS`` lists the values the methodology gives for each factor. Its own worked example uses values that
are not in those lists (motive 2, size 1, ease of exploit 6, intrusion detection 2), so by default any whole
number 0-9 is accepted; ``strict=True`` accepts only the listed options.
"""

from __future__ import annotations

from dataclasses import dataclass

LIKELIHOOD_FACTORS = (
    "skill_level", "motive", "opportunity", "size",  # threat agent
    "ease_of_discovery", "ease_of_exploit", "awareness", "intrusion_detection",  # vulnerability
)
TECHNICAL_FACTORS = ("loss_of_confidentiality", "loss_of_integrity", "loss_of_availability", "loss_of_accountability")
BUSINESS_FACTORS = ("financial_damage", "reputation_damage", "non_compliance", "privacy_violation")

OPTIONS: dict[str, frozenset[int]] = {
    "skill_level": frozenset({1, 3, 5, 6, 9}),
    "motive": frozenset({1, 4, 9}),
    "opportunity": frozenset({0, 4, 7, 9}),
    "size": frozenset({2, 4, 5, 6, 9}),
    "ease_of_discovery": frozenset({1, 3, 7, 9}),
    "ease_of_exploit": frozenset({1, 3, 5, 9}),
    "awareness": frozenset({1, 4, 6, 9}),
    "intrusion_detection": frozenset({1, 3, 8, 9}),
    "loss_of_confidentiality": frozenset({2, 6, 7, 9}),
    "loss_of_integrity": frozenset({1, 3, 5, 7, 9}),
    "loss_of_availability": frozenset({1, 5, 7, 9}),
    "loss_of_accountability": frozenset({1, 7, 9}),
    "financial_damage": frozenset({1, 3, 7, 9}),
    "reputation_damage": frozenset({1, 4, 5, 9}),
    "non_compliance": frozenset({2, 5, 7}),
    "privacy_violation": frozenset({3, 5, 7, 9}),
}

# SEVERITY[impact_level][likelihood_level], from the "Overall Risk Severity" table.
SEVERITY = {
    "HIGH": {"LOW": "Medium", "MEDIUM": "High", "HIGH": "Critical"},
    "MEDIUM": {"LOW": "Low", "MEDIUM": "Medium", "HIGH": "High"},
    "LOW": {"LOW": "Note", "MEDIUM": "Low", "HIGH": "Medium"},
}


@dataclass(frozen=True)
class Rating:
    likelihood: float
    likelihood_level: str
    impact: float
    impact_level: str
    impact_basis: str  # "business" or "technical"
    severity: str


def _average(scores: dict[str, int], names: tuple[str, ...], strict: bool) -> float:
    missing = [n for n in names if n not in scores]
    if missing:
        raise ValueError(f"missing factors: {missing}")
    for n in names:
        value = scores[n]
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 9:
            raise ValueError(f"{n} must be a whole number from 0 to 9, not {value!r}")
        if strict and value not in OPTIONS[n]:
            raise ValueError(f"{n}={value} is not one of the methodology's options {sorted(OPTIONS[n])}")
    return sum(scores[n] for n in names) / len(names)


def level(score: float) -> str:
    """'0 to <3' LOW, '3 to <6' MEDIUM, '6 to 9' HIGH."""
    if not 0 <= score <= 9:
        raise ValueError("score must be between 0 and 9")
    return "LOW" if score < 3 else "MEDIUM" if score < 6 else "HIGH"


def likelihood(scores: dict[str, int], strict: bool = False) -> float:
    return _average(scores, LIKELIHOOD_FACTORS, strict)


def impact(scores: dict[str, int], basis: str, strict: bool = False) -> float:
    """basis is 'technical' or 'business'."""
    if basis not in ("technical", "business"):
        raise ValueError("basis must be 'technical' or 'business'")
    return _average(scores, TECHNICAL_FACTORS if basis == "technical" else BUSINESS_FACTORS, strict)


def rate(scores: dict[str, int], strict: bool = False) -> Rating:
    """Rates one finding. Uses business impact when all four business factors are present, otherwise
    technical impact (the methodology: business impact if you have good business information)."""
    lk = likelihood(scores, strict)
    basis = "business" if all(n in scores for n in BUSINESS_FACTORS) else "technical"
    im = impact(scores, basis, strict)
    lk_level, im_level = level(lk), level(im)
    return Rating(lk, lk_level, im, im_level, basis, SEVERITY[im_level][lk_level])
