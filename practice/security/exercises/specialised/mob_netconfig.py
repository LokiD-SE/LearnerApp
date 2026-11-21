"""EXERCISE - audit an Android network security configuration and work out the effective cleartext setting.

The input is the text of ``res/xml/network_security_config.xml`` (see ``BAD_NSC``, ``GOOD_NSC`` and ``NESTED_NSC``
in ``support/mob_fixture.py``). The element and attribute names are the ones the Android documentation lists:
``base-config``, ``domain-config`` (with ``domain includeSubdomains``), ``trust-anchors`` / ``certificates src``,
``pin-set expiration`` / ``pin``, ``debug-overrides`` and ``cleartextTrafficPermitted``.

* ``parse_config(text)`` - return the root. ``ValueError`` for a ``<!DOCTYPE`` or ``<!ENTITY`` declaration, for text
  that is not well-formed XML, and for a root that is not ``network-security-config``.
* ``audit_config(text)`` - a SORTED list of ``(code, where)`` tuples without repeats. ``where`` is ``"base-config"`` or,
  for a ``domain-config`` (at any nesting depth), its domains lower-cased and joined by ``","`` in document order:
    - ``cleartext-base`` - ``base-config`` has ``cleartextTrafficPermitted="true"``;
    - ``cleartext-domain`` - a ``domain-config`` has ``cleartextTrafficPermitted="true"``;
    - ``user-ca-trusted`` - a ``base-config`` or ``domain-config`` ``trust-anchors`` holds ``certificates src="user"``
      (``debug-overrides`` is only used for debuggable builds, so it is NOT reported);
    - ``pin-expiry`` - a ``pin-set`` has an ``expiration`` attribute (the documentation warns it may let attackers bypass pinning);
    - ``pin-no-backup`` - a ``pin-set`` has fewer than two ``pin`` elements (the documentation says to include a backup key).
* ``effective_cleartext(text, target_sdk, host)`` - is cleartext (plain HTTP) permitted to ``host``?
    1. A ``domain`` rule matches the host when the names are equal (case-insensitive) or ``includeSubdomains="true"`` and
       the host ends with ``"." + name``. Among all matching rules use the one with the LONGEST domain name.
    2. Take ``cleartextTrafficPermitted`` from that rule's ``domain-config``; if it is not set, from its parent
       ``domain-config`` (when nested), and so on outwards; then from ``base-config``;
    3. if none sets it, the platform default: cleartext is permitted when ``target_sdk`` is below 28, not permitted from 28.
  Nothing else (certificate transparency, ``usesCleartextTraffic``) is modelled. House rules for a review.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

DTD = re.compile(r"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)


def parse_config(text: str) -> ET.Element:
    raise NotImplementedError("TODO: refuse DTDs, parse, check the root")


def audit_config(text: str) -> list[tuple[str, str]]:
    raise NotImplementedError("TODO: implement the audit")


def effective_cleartext(text: str, target_sdk: int, host: str) -> bool:
    raise NotImplementedError("TODO: find the longest matching rule, then inherit")
