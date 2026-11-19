"""EXERCISE - fill in the functions marked TODO; the tests are tests/foundations/test_threat_attack_tree.py.

Threat modelling, part 3: attack trees (Schneier, "Attack Trees", Dr. Dobb's Journal, December 1999).

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
    raise NotImplementedError("TODO: a leaf is usable unless its flaw is fixed or it needs equipment that is not allowed")


def possible(node: Node, fixed: frozenset[str] = frozenset(), allow_equipment: bool = True) -> bool:
    """Is the goal reachable at all? A leaf is impossible when its flaw is fixed or it needs equipment the
    attacker does not have; OR = any child possible, AND = all children possible."""
    raise NotImplementedError("TODO: leaf - _leaf_ok; OR - any child; AND - all children")


def cheapest(node: Node, fixed: frozenset[str] = frozenset(), allow_equipment: bool = True) -> Attack | None:
    """The cheapest attack as (cost, leaf names in tree order), or None if the goal is impossible.
    OR takes its cheapest possible child (the first one on a tie); AND sums all its children."""
    raise NotImplementedError("TODO: leaf - its cost; OR - the cheapest possible child (first on a tie); AND - sum, or None")


def attacks(node: Node, fixed: frozenset[str] = frozenset(), allow_equipment: bool = True) -> list[Attack]:
    """Every distinct attack (one choice at each OR node on the way), sorted by cost, then leaf names."""

    raise NotImplementedError("TODO: leaf - one attack; OR - every child's attacks; AND - every combination (itertools.product)")


def attacks_under(node: Node, budget: int, fixed: frozenset[str] = frozenset()) -> list[Attack]:
    """The attacks that cost less than ``budget`` (Schneier's "all attacks that cost less than ...")."""
    raise NotImplementedError("TODO: the attacks whose cost is below the budget")
