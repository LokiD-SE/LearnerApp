"""Exercise: foundations/threat_attack_tree.py - Schneier's attack trees: possible, cheapest, all attacks."""

import pytest
from foundations.threat_attack_tree import Node, attacks, attacks_under, cheapest, possible
from threat_fixture import sandpay_attack_tree

pytestmark = pytest.mark.exercise

ALL_PORTAL_FLAWS = frozenset({"idor", "jwt-none", "sqli", "no-rate-limit"})


def small_tree():
    return Node("goal", "or", [
        Node("both", "and", [Node("a", cost=5), Node("b", cost=7)]),
        Node("c", cost=12),
        Node("d", cost=20, equipment=True),
    ])


def test_and_sums_and_or_takes_the_cheapest():
    assert cheapest(small_tree()) == (12, ["a", "b"])  # 5 + 7 = 12 ties with c; the first child wins


def test_all_attacks_sorted():
    assert attacks(small_tree()) == [(12, ["a", "b"]), (12, ["c"]), (20, ["d"])]


def test_no_equipment():
    assert attacks(small_tree(), allow_equipment=False) == [(12, ["a", "b"]), (12, ["c"])]
    assert cheapest(Node("g", "or", [Node("d", cost=1, equipment=True)]), allow_equipment=False) is None


def test_and_with_an_impossible_child_is_impossible():
    tree = Node("g", "and", [Node("x", cost=1), Node("y", cost=1, flaw="idor")])
    assert possible(tree) is True
    assert possible(tree, fixed=frozenset({"idor"})) is False
    assert cheapest(tree, fixed=frozenset({"idor"})) is None
    assert attacks(tree, fixed=frozenset({"idor"})) == []


def test_sandpay_cheapest_attack_moves_as_flaws_are_fixed():
    tree = sandpay_attack_tree()
    assert cheapest(tree) == (10, ["Request another merchant's payment by id"])
    assert cheapest(tree, frozenset({"idor"})) == (20, ["Forge an unsigned ops token"])
    assert cheapest(tree, frozenset({"idor", "jwt-none", "sqli"})) == (
        100, ["Find an ops email address", "Guess without being throttled", "The ops password is a common one"])
    assert cheapest(tree, ALL_PORTAL_FLAWS) == (300, ["Capture traffic on the merchant's network"])
    assert cheapest(tree, ALL_PORTAL_FLAWS, allow_equipment=False) == (5000, ["Bribe a SandPay insider"])
    assert possible(tree, ALL_PORTAL_FLAWS, allow_equipment=False) is True


def test_attacks_under_a_budget():
    under = attacks_under(sandpay_attack_tree(), 100)
    assert [a[0] for a in under] == [10, 20, 40]  # the 100-point attack is not under 100
    assert attacks_under(sandpay_attack_tree(), 100, frozenset({"idor", "sqli"})) == [(20, ["Forge an unsigned ops token"])]
