"""SOLUTION - audit an Android manifest for the settings that decide a few MASVS controls.

Reads the manifest as text; nothing is installed or run. ``parse_manifest`` refuses any DOCTYPE or entity
declaration (a manifest has none, and Python's parsers expand internal entities).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

ANDROID = "{http://schemas.android.com/apk/res/android}"
COMPONENT_TAGS = ("activity", "activity-alias", "service", "receiver", "provider")
DTD = re.compile(r"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)


def attr(element: ET.Element, name: str) -> str | None:
    """The value of ``android:<name>`` on an element, or None when it is not written."""
    return element.get(ANDROID + name)


def parse_manifest(text: str) -> ET.Element:
    if DTD.search(text):
        raise ValueError("DOCTYPE and ENTITY declarations are not accepted")
    try:
        return ET.fromstring(text)
    except ET.ParseError as error:
        raise ValueError(f"not well-formed XML: {error}") from None


def target_sdk(text: str) -> int | None:
    uses = parse_manifest(text).find("uses-sdk")
    value = attr(uses, "targetSdkVersion") if uses is not None else None
    return int(value) if value is not None and value.isdigit() else None


def is_launcher(component: ET.Element) -> bool:
    for intent_filter in component.findall("intent-filter"):
        actions = {attr(a, "name") for a in intent_filter.findall("action")}
        categories = {attr(c, "name") for c in intent_filter.findall("category")}
        if "android.intent.action.MAIN" in actions and "android.intent.category.LAUNCHER" in categories:
            return True
    return False


def audit_manifest(text: str) -> list[tuple[str, str]]:
    root = parse_manifest(text)
    app = root.find("application")
    if app is None:
        return []
    found: set[tuple[str, str]] = set()
    if attr(app, "debuggable") == "true":
        found.add(("debuggable", "application"))
    if attr(app, "allowBackup") != "false" and attr(app, "dataExtractionRules") is None:
        found.add(("backup-allowed", "application"))
    if attr(app, "usesCleartextTraffic") == "true":
        found.add(("cleartext-manifest", "application"))
    for component in app:
        if component.tag not in COMPONENT_TAGS:
            continue
        name = attr(component, "name") or "?"
        exported = attr(component, "exported")
        unprotected = attr(component, "permission") is None
        if exported == "true":
            if unprotected and not is_launcher(component):
                found.add(("exported-open", name))
        elif exported is None and unprotected:
            if component.find("intent-filter") is not None or component.tag == "provider":
                found.add(("exported-undeclared", name))
    return sorted(found)
