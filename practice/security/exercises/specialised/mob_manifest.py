"""EXERCISE - audit an Android manifest for the settings that decide a few MASVS controls.

The manifest is XML text (see ``BAD_MANIFEST`` and ``GOOD_MANIFEST`` in ``support/mob_fixture.py``). Android
attributes live in the namespace ``http://schemas.android.com/apk/res/android``; ``attr`` below reads one.

* ``parse_manifest(text)`` - return the root element. Raise ``ValueError`` when the text holds a ``<!DOCTYPE``
  or ``<!ENTITY`` declaration (a manifest has neither, and Python's parsers expand internal entities), and
  ``ValueError`` when it is not well-formed XML. Never expand an entity.
* ``target_sdk(text)`` - the integer ``android:targetSdkVersion`` of ``<uses-sdk>``, or ``None`` when absent.
* ``audit_manifest(text)`` - return a SORTED list of ``(code, where)`` tuples, without repeats:
    - ``("debuggable", "application")`` when ``android:debuggable`` is ``"true"``;
    - ``("backup-allowed", "application")`` when ``android:allowBackup`` is not ``"false"`` (the documented default
      is ``"true"``) AND the application has no ``android:dataExtractionRules``;
    - ``("cleartext-manifest", "application")`` when ``android:usesCleartextTraffic`` is ``"true"``;
    - for each activity, activity-alias, service, receiver and provider, with ``where`` = its ``android:name``:
        * ``exported-open`` when ``android:exported="true"``, it has no ``android:permission`` and it is not the
          launcher (an intent filter with action ``android.intent.action.MAIN`` and category
          ``android.intent.category.LAUNCHER``);
        * ``exported-undeclared`` when ``android:exported`` is not written, it has no ``android:permission`` and it
          has an ``<intent-filter>`` or is a provider (say it out loud instead of relying on a default).
  A manifest without an ``<application>`` gives ``[]``. House rules for a review, not a verdict.
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
    raise NotImplementedError("TODO: refuse DTDs, then parse")


def target_sdk(text: str) -> int | None:
    raise NotImplementedError("TODO: read targetSdkVersion from <uses-sdk>")


def audit_manifest(text: str) -> list[tuple[str, str]]:
    raise NotImplementedError("TODO: implement the audit")
