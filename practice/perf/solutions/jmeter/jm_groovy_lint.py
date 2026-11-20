"""Lint the scripting in a JMeter plan - the JSR223 advice of the JMeter manual as code (jm_groovy_ exercise 2).

Rules, each reported as ``(rule, element testname)``:

- ``beanshell``: a BeanShell element (BeanShellSampler, BeanShellPreProcessor, ...). Best Practices 16.9:
  "Since JMeter 3.1, we advise switching from BeanShell to JSR223 Test Elements".
- ``not-compilable``: a JSR223 element whose language is not ``groovy``; only a Compilable engine can be
  compiled and cached ("Groovy is one of these, java, beanshell and javascript are not").
- ``uncached``: a JSR223 element with an inline script and ``cacheKey`` ``false`` - compiled on every run.
  (A script FILE is compiled and cached anyway, so it is not reported.)
- ``interpolation``: a cached JSR223 inline script that contains ``${`` - "caching would take only first value
  of ${varName}". Use ``vars.get("varName")`` or Parameters.
- ``script-function``: ``${__BeanShell(`` or ``${__javaScript(`` in any property of an element - interpreted on
  every call; ``${__groovy(`` or a cached JSR223 element is the advised replacement.

Disabled elements (``enabled="false"``) are skipped.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

SLOW_FUNCTIONS = re.compile(r"\$\{__(BeanShell|javaScript)\(")


def _prop(el: ET.Element, name: str) -> str:
    return el.findtext(f"stringProp[@name='{name}']") or ""


def lint(plan: Path | str) -> list[tuple[str, str]]:
    root = ET.parse(plan).getroot()
    findings: set[tuple[str, str]] = set()
    for el in root.iter():
        name = el.get("testname")
        if name is None or el.get("enabled") == "false":
            continue
        if el.tag.startswith("BeanShell"):
            findings.add(("beanshell", name))
        if el.tag.startswith("JSR223"):
            language = _prop(el, "scriptLanguage").lower()
            inline = not _prop(el, "filename")
            cached = _prop(el, "cacheKey") != "false"
            if language not in ("", "groovy"):
                findings.add(("not-compilable", name))
            if inline and not cached:
                findings.add(("uncached", name))
            if inline and cached and "${" in _prop(el, "script"):
                findings.add(("interpolation", name))
        if any(SLOW_FUNCTIONS.search(p.text or "") for p in el.iter("stringProp")):
            findings.add(("script-function", name))
    return sorted(findings)
