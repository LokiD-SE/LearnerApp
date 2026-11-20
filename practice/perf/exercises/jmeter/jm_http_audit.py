"""Audit a JMeter test plan (.jmx) for common HTTP configuration mistakes - EXERCISE.

A .jmx file is XML: every test element is followed by a ``<hashTree>`` holding its children. A configuration
element (HTTP Request Defaults, a Header Manager, a Cookie Manager) applies to the samplers in its scope: the
samplers in the same ``hashTree`` and below. ``plan_scopes`` (given) walks the tree and returns, for every HTTP
sampler, the configuration elements in its scope, nearest first.

``audit(path)`` returns a ``Finding`` for every problem, with one of these rule ids:

| rule                       | finding                                                                          |
| -------------------------- | -------------------------------------------------------------------------------- |
| ``no-defaults``            | the plan has no HTTP Request Defaults (one finding for the plan, element "plan") |
| ``hard-coded-host``        | a sampler sets its own server name without a variable or property (``${``)       |
| ``no-timeouts``            | no connect or no response timeout for a sampler - its own or from defaults       |
| ``java-implementation``    | the effective implementation is ``Java`` (no control over connection reuse)      |
| ``keepalive-off``          | a sampler has Use KeepAlive off                                                  |
| ``auto-redirect-on-post``  | Redirect Automatically on a POST, PUT or PATCH (the HttpClient sampler rejects it)|
| ``embedded-resources``     | Retrieve All Embedded Resources is on (an API test does not want it)             |
| ``missing-content-type``   | a POST, PUT or PATCH sends a body but no Header Manager in scope sets Content-Type|
| ``several-cookie-managers``| more than one Cookie Manager in a sampler's scope                                |

Run: .venv/bin/python -m pytest tests/jmeter/test_jm_http_audit.py
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

BODY_METHODS = ("POST", "PUT", "PATCH")


@dataclass(frozen=True)
class Finding:
    rule: str
    element: str  # the sampler's name (testname), or "plan"
    message: str


@dataclass
class SamplerScope:
    sampler: ET.Element  # the HTTPSamplerProxy element
    config: list[ET.Element]  # configuration elements in its scope, nearest first (its own children first)


# ---- given: reading a plan ---------------------------------------------------------------------------------
def props(element: ET.Element) -> dict[str, str]:
    """The element's own direct ``stringProp``/``boolProp``/``intProp`` values (not nested ones)."""
    return {p.get("name"): (p.text or "") for p in element if p.tag in ("stringProp", "boolProp", "intProp")}


def is_defaults(element: ET.Element) -> bool:
    return element.tag == "ConfigTestElement" and element.get("guiclass") == "HttpDefaultsGui"


def header_names(element: ET.Element) -> set[str]:
    """Lower-case header names set by a HeaderManager element."""
    return {(h.findtext("stringProp[@name='Header.name']") or "").strip().lower()
            for h in element.iter("elementProp") if h.get("elementType") == "Header"}


def has_body(sampler: ET.Element) -> bool:
    """True when the sampler sends Body Data or unnamed (body) arguments with a value."""
    for arg in sampler.iter("elementProp"):
        if arg.get("elementType") == "HTTPArgument":
            name = arg.findtext("stringProp[@name='Argument.name']") or ""
            value = arg.findtext("stringProp[@name='Argument.value']") or ""
            if not name and value.strip():
                return True
    return False


def plan_scopes(path: Path | str) -> tuple[ET.Element, list[SamplerScope]]:
    """Parses a .jmx and returns (root, one SamplerScope per enabled HTTP sampler, in plan order)."""
    root = ET.parse(path).getroot()
    scopes: list[SamplerScope] = []

    def walk(tree: ET.Element, inherited: list[ET.Element]) -> None:
        children = list(tree)
        pairs = [(children[i], children[i + 1] if i + 1 < len(children) else ET.Element("hashTree"))
                 for i in range(0, len(children), 2)]
        pairs = [(e, t) for e, t in pairs if e.get("enabled", "true") != "false"]
        here = [e for e, _ in pairs if e.tag in ("ConfigTestElement", "HeaderManager", "CookieManager",
                                                  "CacheManager")]
        visible = here + inherited  # nearest first
        for element, subtree in pairs:
            if element.tag == "HTTPSamplerProxy":
                own = [c for c in subtree if c.tag in ("ConfigTestElement", "HeaderManager", "CookieManager",
                                                       "CacheManager") and c.get("enabled", "true") != "false"]
                scopes.append(SamplerScope(element, own + visible))
            else:
                walk(subtree, visible)

    walk(root.find("hashTree"), [])
    return root, scopes


# ---- your part ---------------------------------------------------------------------------------------------
def effective(scope: SamplerScope, name: str) -> str:
    """The value a sampler really uses for ``name`` (e.g. "HTTPSampler.response_timeout"): its own non-empty
    value, else the nearest HTTP Request Defaults in scope with a non-empty value, else ""."""
    # TODO: props(scope.sampler) first; then scope.config in order (nearest first), only is_defaults elements.
    raise NotImplementedError("effective")


def audit(path: Path | str) -> list[Finding]:
    """Every finding for the plan at ``path`` - see the rule table at the top of this file.

    Hints: ``root, scopes = plan_scopes(path)``; the plan-level rule looks at the whole tree
    (``root.iter("ConfigTestElement")``); every other rule looks at one sampler: its own ``props`` and, through
    ``effective`` or ``scope.config``, what is in its scope. A missing boolean property means the GUI default:
    keep-alive on, redirects and embedded resources off. The method defaults to GET.
    """
    # TODO: implement the nine rules.
    raise NotImplementedError("audit")
