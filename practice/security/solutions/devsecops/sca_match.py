"""Reference solution - match an inventory against advisories and rank what is left."""

from __future__ import annotations

import re
from dataclasses import dataclass

ECOSYSTEMS = {"pypi": "PyPI", "npm": "npm"}


@dataclass(frozen=True)
class Finding:
    advisory_id: str
    name: str
    version: str
    fixed_in: str  # "" when the advisory names no fixed version
    score: float


def parse_version(text: str) -> tuple[int, ...]:
    if not re.fullmatch(r"\d+(\.\d+)*", text):
        raise ValueError(f"not a plain numeric version: {text!r}")
    return tuple(int(part) for part in text.split("."))


def _cmp(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    size = max(len(a), len(b))
    a, b = a + (0,) * (size - len(a)), b + (0,) * (size - len(b))
    return (a > b) - (a < b)


def check(version: str, ranges: list[dict]) -> tuple[bool, str]:
    """(is_affected, fixed_in) for OSV-shaped SEMVER ranges. Events are read in the order given."""
    v = parse_version(version)
    for rng in ranges:
        if rng.get("type") != "SEMVER":
            raise ValueError(f"unsupported range type: {rng.get('type')!r}")
        low = None
        for event in rng["events"]:
            if len(event) != 1:
                raise ValueError("an event object holds exactly one of introduced, fixed, last_affected")
            ((kind, value),) = event.items()
            if kind == "introduced":
                low = (0,) if value == "0" else parse_version(value)
            elif kind in ("fixed", "last_affected") and low is not None:
                high = parse_version(value)
                limit = _cmp(v, high) < 0 if kind == "fixed" else _cmp(v, high) <= 0
                if _cmp(v, low) >= 0 and limit:
                    return True, value if kind == "fixed" else ""
                low = None
        if low is not None and _cmp(v, low) >= 0:
            return True, ""
    return False, ""


def ecosystem_of(purl: str) -> tuple[str, str]:
    """``pkg:pypi/sandpay-json@1.4.0`` -> ``("PyPI", "sandpay-json")``."""
    match = re.fullmatch(r"pkg:([a-z]+)/([^@?#]+)(@[^?#]*)?(\?[^#]*)?(#.*)?", purl)
    if not match:
        raise ValueError(f"not a package URL: {purl!r}")
    kind = match.group(1)
    if kind not in ECOSYSTEMS:
        raise ValueError(f"unsupported package type: {kind!r}")
    return ECOSYSTEMS[kind], match.group(2)


def find_findings(components, advisories: list[dict]) -> list[Finding]:
    """Findings for components with a usable purl, sorted by (advisory id, name).

    A component with no purl, or with a package type this matcher does not know, cannot be matched and is skipped."""
    found: dict[tuple[str, str, str], Finding] = {}
    for comp in components:
        if not comp.purl:
            continue
        try:
            ecosystem, name = ecosystem_of(comp.purl)
        except ValueError:
            continue
        for adv in advisories:
            for affected in adv["affected"]:
                pkg = affected["package"]
                if pkg["ecosystem"] != ecosystem or pkg["name"] != name:
                    continue
                hit, fixed = check(comp.version, affected["ranges"])
                if hit:
                    key = (adv["id"], comp.name, comp.version)
                    found[key] = Finding(adv["id"], comp.name, comp.version, fixed,
                                         adv["database_specific"]["cvss_v4_score"])
    return sorted(found.values(), key=lambda f: (f.advisory_id, f.name))


def rating(score: float) -> str:
    """CVSS v4.0 qualitative severity rating scale: None, Low, Medium, High, Critical."""
    if not 0.0 <= score <= 10.0:
        raise ValueError("a CVSS score is between 0.0 and 10.0")
    if score == 0.0:
        return "None"
    if score < 4.0:
        return "Low"
    if score < 7.0:
        return "Medium"
    if score < 9.0:
        return "High"
    return "Critical"


def priority(score: float, in_kev: bool, epss: float) -> str:
    """The lesson's example policy: P1 if exploited in the wild or EPSS >= 0.5; else P2 High/Critical,
    P3 Medium, P4 the rest."""
    if in_kev or epss >= 0.5:
        return "P1"
    return {"Critical": "P2", "High": "P2", "Medium": "P3"}.get(rating(score), "P4")


def triage(findings: list[Finding], known_exploited: set[str], epss: dict[str, float]) -> list[tuple[str, str, str]]:
    """``(priority, advisory_id, name)`` sorted by priority, then advisory id."""
    rows = [
        (priority(f.score, f.advisory_id in known_exploited, epss.get(f.advisory_id, 0.0)), f.advisory_id, f.name)
        for f in findings
    ]
    return sorted(rows)
