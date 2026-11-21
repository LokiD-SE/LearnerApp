"""SOLUTION - audit an Android network security configuration and work out the effective cleartext setting."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

DTD = re.compile(r"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)


def parse_config(text: str) -> ET.Element:
    if DTD.search(text):
        raise ValueError("DOCTYPE and ENTITY declarations are not accepted")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise ValueError(f"not well-formed XML: {error}") from None
    if root.tag != "network-security-config":
        raise ValueError("the root element must be <network-security-config>")
    return root


def domains_of(config: ET.Element) -> list[ET.Element]:
    return config.findall("domain")


def where_of(config: ET.Element) -> str:
    return ",".join((d.text or "").strip().lower() for d in domains_of(config))


def uses_user_ca(config: ET.Element) -> bool:
    anchors = config.find("trust-anchors")
    return anchors is not None and any(c.get("src") == "user" for c in anchors.findall("certificates"))


def all_domain_configs(parent: ET.Element) -> list[ET.Element]:
    found = []
    for child in parent.findall("domain-config"):
        found.append(child)
        found.extend(all_domain_configs(child))
    return found


def audit_config(text: str) -> list[tuple[str, str]]:
    root = parse_config(text)
    found: set[tuple[str, str]] = set()
    base = root.find("base-config")
    if base is not None:
        if base.get("cleartextTrafficPermitted") == "true":
            found.add(("cleartext-base", "base-config"))
        if uses_user_ca(base):
            found.add(("user-ca-trusted", "base-config"))
    for config in all_domain_configs(root):
        where = where_of(config)
        if config.get("cleartextTrafficPermitted") == "true":
            found.add(("cleartext-domain", where))
        if uses_user_ca(config):
            found.add(("user-ca-trusted", where))
        pins = config.find("pin-set")
        if pins is not None:
            if pins.get("expiration") is not None:
                found.add(("pin-expiry", where))
            if len(pins.findall("pin")) < 2:
                found.add(("pin-no-backup", where))
    return sorted(found)


def matches(domain: ET.Element, host: str) -> bool:
    name = (domain.text or "").strip().lower()
    if host == name:
        return True
    return domain.get("includeSubdomains") == "true" and host.endswith("." + name)


def effective_cleartext(text: str, target_sdk: int, host: str) -> bool:
    root = parse_config(text)
    host = host.strip().lower()
    best = None  # (domain length, config, chain of parents)

    def walk(parent: ET.Element, chain: list[ET.Element]) -> None:
        nonlocal best
        for config in parent.findall("domain-config"):
            for domain in domains_of(config):
                if matches(domain, host):
                    length = len((domain.text or "").strip())
                    if best is None or length > best[0]:
                        best = (length, [config] + chain)
            walk(config, [config] + chain)

    walk(root, [])
    chain = best[1] if best else []
    for config in chain:
        value = config.get("cleartextTrafficPermitted")
        if value is not None:
            return value == "true"
    base = root.find("base-config")
    if base is not None and base.get("cleartextTrafficPermitted") is not None:
        return base.get("cleartextTrafficPermitted") == "true"
    return target_sdk < 28
