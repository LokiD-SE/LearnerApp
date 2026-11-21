"""EXERCISE - read two SBOM formats into one inventory and walk the dependency graph.

``Component`` is the common shape. Fill in the five functions; the tests use the synthetic documents in
``support/sca_fixture.py``.

* ``parse_cyclonedx(doc)`` - every entry of ``components``, including nested ``components`` at any depth, but not
  ``metadata.component`` (that is the application itself). ``supplier`` is ``supplier.name``; a missing version,
  purl or supplier is ``""``. Sorted by ``(name, version)``. Raise ``ValueError`` unless
  ``bomFormat == "CycloneDX"``.
* ``parse_spdx(doc)`` - every package except the one(s) the document DESCRIBES (a ``DESCRIBES`` relationship from
  the document's own ``SPDXID``, or ``documentDescribes``). ``purl`` is the ``referenceLocator`` of the
  external reference whose ``referenceType`` is ``purl``. ``supplier`` has its ``Organization: `` or ``Person: ``
  prefix removed, and ``NOASSERTION`` (or no supplier) means ``""``. Sorted like the CycloneDX list. Raise
  ``ValueError`` unless ``spdxVersion`` starts with ``SPDX-``.
* ``transitive_closure(graph, start)`` - the set of nodes reachable from ``start`` (``graph`` maps a node to the
  list of nodes it depends on), not including ``start``. It must finish on a graph with a cycle.
* ``split_direct_transitive(doc)`` - ``(direct, transitive)``: sorted lists of ``bom-ref`` values for the
  CycloneDX document's root (``metadata.component``), from its ``dependencies`` graph. A component the root
  depends on directly is direct even if something else also needs it.
* ``minimum_gaps(components)`` - ``{"name@version": ["supplier", "version", "purl"]}`` for the components that
  lack any of those (listed in that order); components with nothing missing are left out. The key is just the
  name when there is no version.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Component:
    name: str
    version: str  # "" when the document gives none
    purl: str  # "" when the document gives none
    supplier: str  # "" when the document gives none (or SPDX says NOASSERTION)


def parse_cyclonedx(doc: dict) -> list[Component]:
    raise NotImplementedError("TODO: implement parse_cyclonedx")


def parse_spdx(doc: dict) -> list[Component]:
    raise NotImplementedError("TODO: implement parse_spdx")


def transitive_closure(graph: dict[str, list[str]], start: str) -> set[str]:
    raise NotImplementedError("TODO: implement transitive_closure")


def split_direct_transitive(doc: dict) -> tuple[list[str], list[str]]:
    raise NotImplementedError("TODO: implement split_direct_transitive")


def minimum_gaps(components: list[Component]) -> dict[str, list[str]]:
    raise NotImplementedError("TODO: implement minimum_gaps")
