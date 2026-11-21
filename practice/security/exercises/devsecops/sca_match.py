"""EXERCISE - match an inventory against OSV-shaped advisories and rank what is left.

The tests use the synthetic advisories in ``support/sca_fixture.py``. Versions here are plain numbers such as
``1.4.2`` (no pre-release or build parts); real ecosystems have richer rules.

* ``parse_version(text)`` - ``"1.4.2"`` -> ``(1, 4, 2)``. Raise ``ValueError`` for anything that is not dots and
  digits (``"1.4.2rc1"``, ``""``, ``"v1"``). Compare numbers, never strings: 2.9.0 is OLDER than 2.10.0.
* ``check(version, ranges)`` - ``(is_affected, fixed_in)`` for OSV ``ranges`` of ``type`` ``"SEMVER"``. Read the
  ``events`` in order: ``introduced`` opens a range (``"0"`` sorts before everything), ``fixed`` closes it
  EXCLUSIVELY, ``last_affected`` closes it INCLUSIVELY, and a range never closed stays open for ever. Missing
  trailing zeros do not matter (``1.4`` equals ``1.4.0``). ``fixed_in`` is the ``fixed`` value of the range that
  matched, or ``""`` (no ``fixed`` event). Raise ``ValueError`` for a range type other than ``"SEMVER"`` and for an
  event object with more than one key.
* ``ecosystem_of(purl)`` - ``"pkg:pypi/sandpay-json@1.4.0"`` -> ``("PyPI", "sandpay-json")``; ``pkg:npm/...`` ->
  ``"npm"`` (the names in ``ECOSYSTEMS``). Raise ``ValueError`` for text that is not a ``pkg:`` URL or for a type
  not in ``ECOSYSTEMS``.
* ``find_findings(components, advisories)`` - a ``Finding`` for each component an advisory affects, matching on
  ecosystem AND name (the same name in another ecosystem is a different package), sorted by
  ``(advisory_id, name)``. The score comes from ``database_specific.cvss_v4_score``. A component with no purl, or
  an unsupported package type, cannot be matched: skip it.
* ``rating(score)`` - the CVSS v4.0 qualitative scale: 0.0 None, 0.1-3.9 Low, 4.0-6.9 Medium, 7.0-8.9 High,
  9.0-10.0 Critical. ``ValueError`` outside 0.0-10.0.
* ``priority(score, in_kev, epss)`` - this lesson's EXAMPLE policy, not a standard: ``"P1"`` if ``in_kev`` or
  ``epss >= 0.5``; otherwise ``"P2"`` for High and Critical, ``"P3"`` for Medium, ``"P4"`` for the rest.
* ``triage(findings, known_exploited, epss)`` - ``(priority, advisory_id, name)`` rows sorted by priority, then
  advisory id; a finding missing from the ``epss`` dict has EPSS 0.0.
"""

from __future__ import annotations

from dataclasses import dataclass

ECOSYSTEMS = {"pypi": "PyPI", "npm": "npm"}


@dataclass(frozen=True)
class Finding:
    advisory_id: str
    name: str
    version: str
    fixed_in: str  # "" when the advisory names no fixed version
    score: float


def parse_version(text: str) -> tuple[int, ...]:
    raise NotImplementedError("TODO: implement parse_version")


def check(version: str, ranges: list[dict]) -> tuple[bool, str]:
    raise NotImplementedError("TODO: implement check")


def ecosystem_of(purl: str) -> tuple[str, str]:
    raise NotImplementedError("TODO: implement ecosystem_of")


def find_findings(components, advisories: list[dict]) -> list[Finding]:
    raise NotImplementedError("TODO: implement find_findings")


def rating(score: float) -> str:
    raise NotImplementedError("TODO: implement rating")


def priority(score: float, in_kev: bool, epss: float) -> str:
    raise NotImplementedError("TODO: implement priority")


def triage(findings: list[Finding], known_exploited: set[str], epss: dict[str, float]) -> list[tuple[str, str, str]]:
    raise NotImplementedError("TODO: implement triage")
