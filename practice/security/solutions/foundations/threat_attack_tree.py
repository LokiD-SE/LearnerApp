"""Threat modelling, part 3: attack trees (Schneier, "Attack Trees", Dr. Dobb's Journal, December 1999).

The goal is the root; children are ways to reach it. An OR node is reached if ANY child is; an AND node only
if ALL children are. Leaf costs propagate up: "OR nodes have the value of their cheapest child; AND nodes have
the value of the sum of their children."

Leaves here can name the portal flaw they rely on (``flaw``, an id from support/sandpay_vuln.py). Fixing that
flaw makes the leaf impossible, so you can ask "what is the cheapest attack left after these fixes?". Leaves can
also need special equipment, which an attacker profile may not have (Schneier's Figure 6 asks for "the cheapest
attack requiring no special equipment").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product

Attack = tuple[int, list[str]]  # (total cost, leaf names in tree order)


@dataclass
class Node:
    name: str
    kind: str = "leaf"  # "leaf", "and" or "or"
    children: list["Node"] = field(default_factory=list)
    cost: int = 0  # leaves only
    equipment: bool = False  # leaves only: needs special equipment
    flaw: str | None = None  # leaves only: the portal flaw this step relies on


def _leaf_ok(node: Node, fixed: frozenset[str], allow_equipment: bool) -> bool:
    return not (node.flaw is not None and node.flaw in fixed) and (allow_equipment or not node.equipment)


def possible(node: Node, fixed: frozenset[str] = frozenset(), allow_equipment: bool = True) -> bool:
    """Is the goal reachable at all? A leaf is impossible when its flaw is fixed or it needs equipment the
    attacker does not have; OR = any child possible, AND = all children possible."""
    if node.kind == "leaf":
        return _leaf_ok(node, fixed, allow_equipment)
    results = [possible(c, fixed, allow_equipment) for c in node.children]
    return any(results) if node.kind == "or" else all(results)


def cheapest(node: Node, fixed: frozenset[str] = frozenset(), allow_equipment: bool = True) -> Attack | None:
    """The cheapest attack as (cost, leaf names in tree order), or None if the goal is impossible.
    OR takes its cheapest possible child (the first one on a tie); AND sums all its children."""
    if node.kind == "leaf":
        return (node.cost, [node.name]) if _leaf_ok(node, fixed, allow_equipment) else None
    options = [cheapest(c, fixed, allow_equipment) for c in node.children]
    if node.kind == "or":
        found = [o for o in options if o is not None]
        return min(found, key=lambda o: o[0]) if found else None
    if any(o is None for o in options):
        return None
    return sum(o[0] for o in options), [leaf for o in options for leaf in o[1]]


def attacks(node: Node, fixed: frozenset[str] = frozenset(), allow_equipment: bool = True) -> list[Attack]:
    """Every distinct attack (one choice at each OR node on the way), sorted by cost, then leaf names."""

    def walk(n: Node) -> list[Attack]:
        if n.kind == "leaf":
            return [(n.cost, [n.name])] if _leaf_ok(n, fixed, allow_equipment) else []
        child_lists = [walk(c) for c in n.children]
        if n.kind == "or":
            return [a for lst in child_lists for a in lst]
        return [(sum(a[0] for a in combo), [leaf for a in combo for leaf in a[1]]) for combo in product(*child_lists)]

    return sorted(walk(node), key=lambda a: (a[0], a[1]))


def attacks_under(node: Node, budget: int, fixed: frozenset[str] = frozenset()) -> list[Attack]:
    """The attacks that cost less than ``budget`` (Schneier's "all attacks that cost less than ...")."""
    return [a for a in attacks(node, fixed) if a[0] < budget]
