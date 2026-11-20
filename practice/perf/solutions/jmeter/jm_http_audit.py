"""Audit a JMeter test plan (.jmx) for common HTTP configuration mistakes - reference solution.

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


# ---- the learner's part ------------------------------------------------------------------------------------
def effective(scope: SamplerScope, name: str) -> str:
    """The value a sampler really uses for ``name`` (e.g. "HTTPSampler.response_timeout"): its own non-empty
    value, else the nearest HTTP Request Defaults in scope with a non-empty value, else ""."""
    own = props(scope.sampler).get(name, "")
    if own.strip():
        return own
    for element in scope.config:
        if is_defaults(element):
            value = props(element).get(name, "")
            if value.strip():
                return value
    return ""


def audit(path: Path | str) -> list[Finding]:
    root, scopes = plan_scopes(path)
    findings: list[Finding] = []
    if not any(is_defaults(e) for e in root.iter("ConfigTestElement")):
        findings.append(Finding("no-defaults", "plan", "no HTTP Request Defaults - server, port and timeouts are "
                                                       "repeated in (or missing from) every sampler"))
    for scope in scopes:
        name = scope.sampler.get("testname", "?")
        own = props(scope.sampler)
        method = own.get("HTTPSampler.method", "GET").upper()
        domain = own.get("HTTPSampler.domain", "")
        if domain.strip() and "${" not in domain:
            findings.append(Finding("hard-coded-host", name, f"server '{domain}' is hard-coded in the sampler"))
        for timeout in ("HTTPSampler.connect_timeout", "HTTPSampler.response_timeout"):
            if not effective(scope, timeout).strip():
                findings.append(Finding("no-timeouts", name, f"no {timeout.split('.')[1]} - a hung server "
                                                             "blocks the thread"))
        if effective(scope, "HTTPSampler.implementation").strip().lower() == "java":
            findings.append(Finding("java-implementation", name, "Java implementation - no control over "
                                                                 "connection reuse"))
        if own.get("HTTPSampler.use_keepalive", "true").strip().lower() == "false":
            findings.append(Finding("keepalive-off", name, "Use KeepAlive is off - a new connection per request"))
        if method in BODY_METHODS and own.get("HTTPSampler.auto_redirects", "false").strip().lower() == "true":
            findings.append(Finding("auto-redirect-on-post", name, f"Redirect Automatically on {method}"))
        if own.get("HTTPSampler.image_parser", "false").strip().lower() == "true":
            findings.append(Finding("embedded-resources", name, "Retrieve All Embedded Resources is on"))
        if method in BODY_METHODS and has_body(scope.sampler):
            if not any("content-type" in header_names(e) for e in scope.config if e.tag == "HeaderManager"):
                findings.append(Finding("missing-content-type", name, f"{method} with a body and no Content-Type"))
        cookie_managers = [e for e in scope.config if e.tag == "CookieManager"]
        if len(cookie_managers) > 1:
            findings.append(Finding("several-cookie-managers", name, f"{len(cookie_managers)} Cookie Managers in "
                                                                     "scope - JMeter cannot say which is used"))
    return findings
