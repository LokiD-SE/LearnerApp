"""CVSS v3.1 base score from a vector string - the formulas of FIRST's specification, section 7.

The v3.1 equations and the metric weights are from https://www.first.org/cvss/v3.1/specification-document
(read on 21 November 2026). ``roundup`` follows Appendix A, which avoids floating point surprises.
"""

from __future__ import annotations

from cvss_fixture import V31_ORDER, V31_VALUES

PREFIX = "CVSS:3.1/"

WEIGHTS = {
    "AV": {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2},
    "AC": {"L": 0.77, "H": 0.44},
    "UI": {"N": 0.85, "R": 0.62},
    "CIA": {"H": 0.56, "L": 0.22, "N": 0.0},
}
PR_UNCHANGED = {"N": 0.85, "L": 0.62, "H": 0.27}
PR_CHANGED = {"N": 0.85, "L": 0.68, "H": 0.5}


def parse_vector(text: str) -> dict[str, str]:
    """``CVSS:3.1/AV:N/...`` -> ``{"AV": "N", ...}``. The eight base metrics, in any order, each once."""
    if not text.startswith(PREFIX):
        raise ValueError("a CVSS v3.1 vector starts with 'CVSS:3.1/'")
    metrics: dict[str, str] = {}
    for part in text[len(PREFIX):].split("/"):
        name, sep, value = part.partition(":")
        if not sep or name not in V31_VALUES:
            raise ValueError(f"not a base metric: {part!r}")
        if name in metrics:
            raise ValueError(f"metric {name} appears more than once")
        if len(value) != 1 or value not in V31_VALUES[name]:
            raise ValueError(f"{value!r} is not a valid value for {name}")
        metrics[name] = value
    missing = [name for name in V31_ORDER if name not in metrics]
    if missing:
        raise ValueError(f"missing base metrics: {', '.join(missing)}")
    return metrics


def roundup(value: float) -> float:
    """The smallest number with one decimal place that is >= value (Appendix A, integer arithmetic)."""
    as_int = round(value * 100000)
    if as_int % 10000 == 0:
        return as_int / 100000.0
    return (as_int // 10000 + 1) / 10.0


def base_score(vector: str) -> float:
    m = parse_vector(vector)
    changed = m["S"] == "C"
    iss = 1 - (1 - WEIGHTS["CIA"][m["C"]]) * (1 - WEIGHTS["CIA"][m["I"]]) * (1 - WEIGHTS["CIA"][m["A"]])
    impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15 if changed else 6.42 * iss
    pr = (PR_CHANGED if changed else PR_UNCHANGED)[m["PR"]]
    exploitability = 8.22 * WEIGHTS["AV"][m["AV"]] * WEIGHTS["AC"][m["AC"]] * pr * WEIGHTS["UI"][m["UI"]]
    if impact <= 0:
        return 0.0
    total = impact + exploitability
    return roundup(min(1.08 * total if changed else total, 10))
