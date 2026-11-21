"""CVSS v4.0 base scoring (CVSS-B, plus Exploit Maturity for CVSS-BT) from a vector string.

The vector rules are the specification's Table 23 (https://www.first.org/cvss/v4.0/specification-document, read on
21 November 2026): the prefix ``CVSS:4.0/``, every base metric, in this order, each once. The scoring is FIRST's
macro vector method: six equivalence classes pick a row of a lookup table, and ``cvss_fixture.interpolate`` moves
the score down from that row's maximum by the vector's distance to the highest severity vectors of its group.
"""

from __future__ import annotations

from cvss_fixture import V4_ORDER, V4_THREAT_VALUES, V4_VALUES, interpolate

PREFIX = "CVSS:4.0/"


def parse_vector(text: str) -> dict[str, str]:
    """Return the base metrics (and ``E``, default ``X``) as a dict; raise ``ValueError`` on any rule break."""
    if not text.startswith(PREFIX):
        raise ValueError("a CVSS v4.0 vector starts with 'CVSS:4.0/'")
    parts = text[len(PREFIX):].split("/")
    metrics: dict[str, str] = {}
    expected = list(V4_ORDER)
    for part in parts:
        name, sep, value = part.partition(":")
        if not sep:
            raise ValueError(f"not a metric: {part!r}")
        if name in metrics:
            raise ValueError(f"metric {name} appears more than once")
        if name == "E":
            if expected:
                raise ValueError(f"mandatory metric {expected[0]} is missing")
            if value not in V4_THREAT_VALUES or len(value) != 1:
                raise ValueError(f"{value!r} is not a valid value for E")
        elif name in V4_VALUES:
            if not expected or name != expected[0]:
                raise ValueError(f"metric {name} is out of order or missing a predecessor")
            if len(value) != 1 or value not in V4_VALUES[name]:
                raise ValueError(f"{value!r} is not a valid value for {name}")
            expected.pop(0)
        else:
            raise ValueError(f"not a supported metric: {name!r} (this module scores base metrics and E)")
        metrics[name] = value
    if expected:
        raise ValueError(f"mandatory metric {expected[0]} is missing")
    metrics.setdefault("E", "X")
    return metrics


def macrovector(m: dict[str, str]) -> str:
    """The six-digit macro vector EQ1..EQ6 of a parsed vector (Confidentiality/Integrity/Availability
    Requirements are Not Defined, which counts as High; E Not Defined counts as Attacked)."""
    av, pr, ui = m["AV"], m["PR"], m["UI"]
    if av == "N" and pr == "N" and ui == "N":
        eq1 = 0
    elif (av == "N" or pr == "N" or ui == "N") and av != "P":
        eq1 = 1
    else:
        eq1 = 2
    eq2 = 0 if m["AC"] == "L" and m["AT"] == "N" else 1
    if m["VC"] == "H" and m["VI"] == "H":
        eq3 = 0
    elif "H" in (m["VC"], m["VI"], m["VA"]):
        eq3 = 1
    else:
        eq3 = 2
    eq4 = 1 if "H" in (m["SC"], m["SI"], m["SA"]) else 2
    eq5 = {"X": 0, "A": 0, "P": 1, "U": 2}[m["E"]]
    eq6 = 0 if "H" in (m["VC"], m["VI"], m["VA"]) else 1
    return f"{eq1}{eq2}{eq3}{eq4}{eq5}{eq6}"


def score(vector: str) -> float:
    m = parse_vector(vector)
    return interpolate(m, macrovector(m))
