"""EXERCISE - fill in the functions marked TODO; the tests are tests/foundations/test_threat_dfd.py.

Threat modelling, part 1: a data flow diagram (DFD), STRIDE per element, and a threat register check.

Sources (see the lesson for links):
- STRIDE per element: the "Threats Affecting Elements" table in Hernan, Lambert, Ostwald and Shostack,
  "Uncover Security Design Flaws Using The STRIDE Approach", MSDN Magazine, November 2006:
  data flows and data stores - T, I, D; processes - all six; interactors (external entities) - S, R.
- The DFD rules of thumb come from the same article: no "magic data sources or sinks" (every data store is
  written and read by a process), no "psychokinesis as a data transport" (a process at one end of every flow).
- Threat responses (mitigate, eliminate, transfer, accept) and turning mitigations into requirements and tests:
  the OWASP Threat Modeling Cheat Sheet.
"""

from __future__ import annotations

from dataclasses import dataclass, field

STRIDE = ("S", "T", "R", "I", "D", "E")
CATEGORY = {
    "S": "Spoofing",
    "T": "Tampering",
    "R": "Repudiation",
    "I": "Information disclosure",
    "D": "Denial of service",
    "E": "Elevation of privilege",
}
# The property each category violates (MSDN 2006, Figure 3).
PROPERTY = {
    "S": "Authentication",
    "T": "Integrity",
    "R": "Non-repudiation",
    "I": "Confidentiality",
    "D": "Availability",
    "E": "Authorization",
}
KINDS = ("interactor", "process", "data_store", "data_flow")
RESPONSES = ("mitigate", "eliminate", "transfer", "accept")


@dataclass(frozen=True)
class Element:
    id: str
    name: str
    kind: str  # one of KINDS
    source: str | None = None  # data flows only: the element the data comes from
    target: str | None = None  # data flows only: the element the data goes to


@dataclass(frozen=True)
class Boundary:
    name: str
    inside: frozenset[str]  # ids of the interactors, processes and data stores inside it


@dataclass
class Dfd:
    elements: list[Element]
    boundaries: list[Boundary] = field(default_factory=list)

    def get(self, element_id: str) -> Element | None:
        return next((e for e in self.elements if e.id == element_id), None)


@dataclass(frozen=True)
class Threat:
    element_id: str
    category: str  # one letter of STRIDE
    crosses: tuple[str, ...] = ()  # names of the trust boundaries a data flow crosses


def stride_for(kind: str) -> tuple[str, ...]:
    """The STRIDE categories that apply to an element kind, in S-T-R-I-D-E order (MSDN 2006, Figure 5)."""
    raise NotImplementedError("TODO: return the STRIDE letters for this kind from the MSDN 2006 'Threats Affecting Elements' table")


def crossings(dfd: Dfd, flow: Element) -> tuple[str, ...]:
    """Names of the trust boundaries a data flow crosses: exactly one of its two ends is inside the boundary."""
    raise NotImplementedError("TODO: names of the boundaries where exactly one end of the flow is inside")


def enumerate_threats(dfd: Dfd) -> list[Threat]:
    """One threat per (element, applicable STRIDE category), in element order then S-T-R-I-D-E order.

    Data flow threats carry the boundaries the flow crosses - those flows are where an attacker's input
    enters, so they are reviewed first."""
    raise NotImplementedError("TODO: one Threat per element and applicable category; flows carry their crossings")


def check_dfd(dfd: Dfd) -> list[str]:
    """Problems with the diagram itself, as ``"<code>: <element id>"`` strings in element order.

    - ``unknown-kind``: an element kind outside KINDS;
    - ``bad-endpoint``: a flow's source or target is missing, unknown, or another data flow;
    - ``no-process``: neither end of a flow is a process ("psychokinesis as a data transport");
    - ``never-written`` / ``never-read``: a data store with no flow into it / out of it (a magic source/sink).
    """
    raise NotImplementedError("TODO: apply the four rules in the docstring and return the problem strings in order")


def check_register(register: list[dict]) -> list[str]:
    """Problems with a threat register, as ``"<code>: <threat id>"`` strings in register order.

    Each entry has ``id``, ``category`` (a STRIDE letter) and ``response`` (one of RESPONSES), plus:
    ``mitigate`` needs a ``requirement`` and a ``test`` (how we will know the mitigation works);
    ``transfer`` needs an ``owner`` (who now holds the remaining controls); ``accept`` needs a ``reason``
    and an ``owner`` (who accepted the residual risk). ``eliminate`` needs nothing more.
    Codes: ``bad-category``, ``no-response``, ``no-requirement``, ``no-test``, ``no-owner``, ``no-reason``.
    """
    raise NotImplementedError("TODO: check each entry's category and response, and what each response needs")
