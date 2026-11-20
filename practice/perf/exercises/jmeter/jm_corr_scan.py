"""Finds correlation problems in a JMeter plan before it runs - EXERCISE.

A recorded plan replays the values the server sent during recording: an old bearer token, the payment ids
and cursors of that session. ``scan(jmx_text)`` reads the .jmx (it is XML) and reports:

- ``hardcoded-token``: an ``Authorization`` header whose value has no ``${...}`` reference;
- ``hardcoded-id``: a sampler path or argument that contains a literal SandPay payment id (``pay_`` and
  digits) instead of a variable;
- ``never-set``: a ``${name}`` used in a header, path or argument that nothing in the plan sets - no
  extractor, no User Defined Variable, no CSV Data Set. Functions such as ``${__P(port,8090)}`` are not
  variables;
- ``no-default``: an extractor with an empty default value, so a failed extraction is hard to see.

Run: .venv/bin/python -m pytest tests/jmeter/test_jm_corr_scan.py

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
    """The text of a child ``<stringProp name="...">``, or "" (given - use it)."""
    found = element.find(f"stringProp[@name='{name}']")
    return (found.text or "") if found is not None else ""


def defined_variables(root: ET.Element) -> set[str]:
    """Every variable name something in the plan sets: extractors (EXTRACTORS; JSON names are ``;``-separated),
    User Defined Variables (``elementProp`` with ``elementType="Argument"``: ``Argument.name``) and CSV Data
    Sets (``CSVDataSet``: ``variableNames``, comma-separated)."""
    raise NotImplementedError("TODO: collect the names the plan sets")


def scan(jmx_text: str) -> list[tuple[str, str, str]]:
    """Returns the sorted findings described above."""
    raise NotImplementedError("TODO: hardcoded-token, hardcoded-id, never-set, no-default")
