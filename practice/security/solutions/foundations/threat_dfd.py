"""Threat modelling, part 1: a data flow diagram (DFD), STRIDE per element, and a threat register check.

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
    table = {
        "data_flow": ("T", "I", "D"),
        "data_store": ("T", "I", "D"),
        "process": STRIDE,
        "interactor": ("S", "R"),
    }
    if kind not in table:
        raise ValueError(f"unknown element kind {kind!r}; expected one of {KINDS}")
    return table[kind]


def crossings(dfd: Dfd, flow: Element) -> tuple[str, ...]:
    """Names of the trust boundaries a data flow crosses: exactly one of its two ends is inside the boundary."""
    return tuple(b.name for b in dfd.boundaries if (flow.source in b.inside) != (flow.target in b.inside))


def enumerate_threats(dfd: Dfd) -> list[Threat]:
    """One threat per (element, applicable STRIDE category), in element order then S-T-R-I-D-E order.

    Data flow threats carry the boundaries the flow crosses - those flows are where an attacker's input
    enters, so they are reviewed first."""
    threats: list[Threat] = []
    for e in dfd.elements:
        crossed = crossings(dfd, e) if e.kind == "data_flow" else ()
        threats += [Threat(e.id, c, crossed) for c in stride_for(e.kind)]
    return threats


def check_dfd(dfd: Dfd) -> list[str]:
    """Problems with the diagram itself, as ``"<code>: <element id>"`` strings in element order.

    - ``unknown-kind``: an element kind outside KINDS;
    - ``bad-endpoint``: a flow's source or target is missing, unknown, or another data flow;
    - ``no-process``: neither end of a flow is a process ("psychokinesis as a data transport");
    - ``never-written`` / ``never-read``: a data store with no flow into it / out of it (a magic source/sink).
    """
    problems: list[str] = []
    flows = [e for e in dfd.elements if e.kind == "data_flow"]
    for e in dfd.elements:
        if e.kind not in KINDS:
            problems.append(f"unknown-kind: {e.id}")
            continue
        if e.kind != "data_flow":
            continue
        ends = [dfd.get(e.source) if e.source else None, dfd.get(e.target) if e.target else None]
        if any(end is None or end.kind == "data_flow" for end in ends):
            problems.append(f"bad-endpoint: {e.id}")
            continue
        if all(end.kind != "process" for end in ends):
            problems.append(f"no-process: {e.id}")
    for e in dfd.elements:
        if e.kind == "data_store":
            if not any(f.target == e.id for f in flows):
                problems.append(f"never-written: {e.id}")
            if not any(f.source == e.id for f in flows):
                problems.append(f"never-read: {e.id}")
    return problems


def check_register(register: list[dict]) -> list[str]:
    """Problems with a threat register, as ``"<code>: <threat id>"`` strings in register order.

    Each entry has ``id``, ``category`` (a STRIDE letter) and ``response`` (one of RESPONSES), plus:
    ``mitigate`` needs a ``requirement`` and a ``test`` (how we will know the mitigation works);
    ``transfer`` needs an ``owner`` (who now holds the remaining controls); ``accept`` needs a ``reason``
    and an ``owner`` (who accepted the residual risk). ``eliminate`` needs nothing more.
    Codes: ``bad-category``, ``no-response``, ``no-requirement``, ``no-test``, ``no-owner``, ``no-reason``.
    """
    problems: list[str] = []
    for entry in register:
        tid = entry.get("id", "?")
        if entry.get("category") not in STRIDE:
            problems.append(f"bad-category: {tid}")
        response = entry.get("response")
        if response not in RESPONSES:
            problems.append(f"no-response: {tid}")
            continue
        if response == "mitigate":
            if not str(entry.get("requirement", "")).strip():
                problems.append(f"no-requirement: {tid}")
            if not str(entry.get("test", "")).strip():
                problems.append(f"no-test: {tid}")
        elif response == "transfer":
            if not str(entry.get("owner", "")).strip():
                problems.append(f"no-owner: {tid}")
        elif response == "accept":
            if not str(entry.get("reason", "")).strip():
                problems.append(f"no-reason: {tid}")
            if not str(entry.get("owner", "")).strip():
                problems.append(f"no-owner: {tid}")
    return problems
