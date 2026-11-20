"""Finds correlation problems in a JMeter plan before it runs - reference solution.

A recorded plan replays the values the server sent during recording: an old bearer token, the payment ids
and cursors of that session. ``scan(jmx_text)`` reads the .jmx (it is XML) and reports:

- ``hardcoded-token``: an ``Authorization`` header whose value has no ``${...}`` reference;
- ``hardcoded-id``: a sampler path or argument that contains a literal SandPay payment id (``pay_`` and
  digits) instead of a variable;
- ``never-set``: a ``${name}`` used in a header, path or argument that nothing in the plan sets - no
  extractor, no User Defined Variable, no CSV Data Set. Functions such as ``${__P(port,8090)}`` are not
  variables;
- ``no-default``: an extractor with an empty default value, so a failed extraction is hard to see.

Each finding is ``(kind, element, detail)`` where ``element`` is the element's ``testname``; results are sorted.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

VAR = re.compile(r"\$\{(?!__)([A-Za-z_][A-Za-z0-9_]*)\}")  # ${__name(...)} is a function, not a variable
PAYMENT_ID = re.compile(r"\bpay_\d+\b")

# element tag -> (property holding the variable name(s), property holding the default(s))
EXTRACTORS = {
    "JSONPostProcessor": ("JSONPostProcessor.referenceNames", "JSONPostProcessor.defaultValues"),
    "RegexExtractor": ("RegexExtractor.refname", "RegexExtractor.default"),
    "BoundaryExtractor": ("BoundaryExtractor.refname", "BoundaryExtractor.default"),
}


def _prop(element: ET.Element, name: str) -> str:
    found = element.find(f"stringProp[@name='{name}']")
    return (found.text or "") if found is not None else ""


def defined_variables(root: ET.Element) -> set[str]:
    """Every variable name something in the plan sets."""
    names: set[str] = set()
    for tag, (ref_prop, _) in EXTRACTORS.items():
        for el in root.iter(tag):
            names.update(n.strip() for n in _prop(el, ref_prop).split(";") if n.strip())
    for arg in root.iter("elementProp"):
        if arg.get("elementType") == "Argument":
            name = _prop(arg, "Argument.name")
            if name:
                names.add(name)
    for csv in root.iter("CSVDataSet"):
        names.update(n.strip() for n in _prop(csv, "variableNames").split(",") if n.strip())
    return names


def scan(jmx_text: str) -> list[tuple[str, str, str]]:
    root = ET.fromstring(jmx_text)
    findings: set[tuple[str, str, str]] = set()
    defined = defined_variables(root)
    used: list[tuple[str, str]] = []  # (element testname, text that may contain ${...})

    for manager in root.iter("HeaderManager"):
        owner = manager.get("testname", "HeaderManager")
        for header in manager.iter("elementProp"):
            if header.get("elementType") != "Header":
                continue
            name, value = _prop(header, "Header.name"), _prop(header, "Header.value")
            used.append((owner, value))
            if name.lower() == "authorization" and "${" not in value:
                findings.add(("hardcoded-token", owner, f"{name}: {value}"))

    for sampler in root.iter("HTTPSamplerProxy"):
        owner = sampler.get("testname", "HTTPSamplerProxy")
        texts = [_prop(sampler, "HTTPSampler.path")]
        texts += [_prop(arg, "Argument.value") for arg in sampler.iter("elementProp")
                  if arg.get("elementType") == "HTTPArgument"]
        for text in texts:
            used.append((owner, text))
            for literal in PAYMENT_ID.findall(text):
                findings.add(("hardcoded-id", owner, literal))

    for owner, text in used:
        for name in VAR.findall(text):
            if name not in defined:
                findings.add(("never-set", owner, name))

    for tag, (ref_prop, default_prop) in EXTRACTORS.items():
        for el in root.iter(tag):
            defaults = _prop(el, default_prop)
            refs = [n for n in _prop(el, ref_prop).split(";") if n.strip()]
            parts = defaults.split(";") if defaults else []
            if not defaults.strip() or len(parts) < len(refs) or any(not p.strip() for p in parts):
                findings.add(("no-default", el.get("testname", tag), ";".join(refs)))

    return sorted(findings)
