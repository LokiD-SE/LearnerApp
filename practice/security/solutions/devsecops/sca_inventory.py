"""Reference solution - read two SBOM formats into one inventory and walk the dependency graph."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Component:
    name: str
    version: str  # "" when the document gives none
    purl: str  # "" when the document gives none
    supplier: str  # "" when the document gives none (or SPDX says NOASSERTION)


def _walk(items):
    for comp in items or []:
        yield comp
        yield from _walk(comp.get("components"))


def parse_cyclonedx(doc: dict) -> list[Component]:
    if doc.get("bomFormat") != "CycloneDX":
        raise ValueError("not a CycloneDX document")
    found = [
        Component(c["name"], c.get("version", ""), c.get("purl", ""), c.get("supplier", {}).get("name", ""))
        for c in _walk(doc.get("components"))
    ]
    return sorted(found, key=lambda c: (c.name, c.version))


def _spdx_supplier(text: str | None) -> str:
    if not text or text == "NOASSERTION":
        return ""
    for prefix in ("Organization: ", "Person: "):
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


def parse_spdx(doc: dict) -> list[Component]:
    if not str(doc.get("spdxVersion", "")).startswith("SPDX-"):
        raise ValueError("not an SPDX document")
    described = {
        r["relatedSpdxElement"]
        for r in doc.get("relationships", [])
        if r["relationshipType"] == "DESCRIBES" and r["spdxElementId"] == doc["SPDXID"]
    }
    described |= set(doc.get("documentDescribes", []))
    found = []
    for pkg in doc.get("packages", []):
        if pkg["SPDXID"] in described:
            continue
        purl = next(
            (ref["referenceLocator"] for ref in pkg.get("externalRefs", []) if ref.get("referenceType") == "purl"),
            "",
        )
        found.append(Component(pkg["name"], pkg.get("versionInfo", ""), purl, _spdx_supplier(pkg.get("supplier"))))
    return sorted(found, key=lambda c: (c.name, c.version))


def transitive_closure(graph: dict[str, list[str]], start: str) -> set[str]:
    """Everything reachable from ``start`` by following edges, not including ``start`` itself (cycle safe)."""
    seen: set[str] = set()
    stack = list(graph.get(start, []))
    while stack:
        node = stack.pop()
        if node in seen or node == start:
            continue
        seen.add(node)
        stack.extend(graph.get(node, []))
    return seen


def split_direct_transitive(doc: dict) -> tuple[list[str], list[str]]:
    """(direct, transitive) bom-refs of the CycloneDX document's root component, each sorted.

    A component the application depends on directly is direct even when something else also needs it."""
    root = doc["metadata"]["component"]["bom-ref"]
    graph = {d["ref"]: list(d.get("dependsOn", [])) for d in doc.get("dependencies", [])}
    direct = set(graph.get(root, []))
    everything = transitive_closure(graph, root)
    return sorted(direct), sorted(everything - direct)


def minimum_gaps(components: list[Component]) -> dict[str, list[str]]:
    """Components missing a supplier, version or package identifier: ``{"name@version": ["supplier", ...]}``.

    The key is ``name@version`` (just ``name`` when there is no version). Fields are listed in the order
    supplier, version, purl. Components with nothing missing are left out."""
    gaps: dict[str, list[str]] = {}
    for comp in components:
        missing = [label for label, value in (("supplier", comp.supplier), ("version", comp.version),
                                              ("purl", comp.purl)) if not value]
        if missing:
            gaps[f"{comp.name}@{comp.version}" if comp.version else comp.name] = missing
    return gaps
