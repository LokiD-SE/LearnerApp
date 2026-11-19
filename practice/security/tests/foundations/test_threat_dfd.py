"""Exercise: foundations/threat_dfd.py - STRIDE per element on a DFD, and checks on the DFD and the register."""

import pytest
from foundations.threat_dfd import Boundary, Dfd, Element, check_dfd, check_register, crossings, enumerate_threats, stride_for
from threat_fixture import sandpay_dfd

pytestmark = pytest.mark.exercise


@pytest.mark.parametrize(
    "kind, expected",
    [
        ("data_flow", ("T", "I", "D")),
        ("data_store", ("T", "I", "D")),
        ("process", ("S", "T", "R", "I", "D", "E")),
        ("interactor", ("S", "R")),
    ],
)
def test_stride_per_element(kind, expected):
    assert stride_for(kind) == expected


def test_unknown_kind_is_an_error():
    with pytest.raises(ValueError):
        stride_for("database")


def test_crossings():
    dfd = sandpay_dfd()
    flow = {e.id: e for e in dfd.elements}
    assert crossings(dfd, flow["f1"]) == ("SandPay network",)  # merchant -> portal
    assert crossings(dfd, flow["f4"]) == ("Database server",)  # portal -> db: both in the network
    assert crossings(dfd, flow["f8"]) == ()  # log -> review: same side of both boundaries
    assert crossings(dfd, flow["f7"]) == ("SandPay network",)  # outbound counts too


def test_enumerate_threats_counts_and_order():
    threats = enumerate_threats(sandpay_dfd())
    # 3 interactors x 2 + 2 processes x 6 + 2 stores x 3 + 9 flows x 3
    assert len(threats) == 6 + 12 + 6 + 27
    assert [(t.element_id, t.category) for t in threats[:3]] == [("merchant", "S"), ("merchant", "R"), ("ops", "S")]
    portal = [t.category for t in threats if t.element_id == "portal"]
    assert portal == ["S", "T", "R", "I", "D", "E"]


def test_flow_threats_carry_crossed_boundaries():
    threats = enumerate_threats(sandpay_dfd())
    f1 = [t for t in threats if t.element_id == "f1"]
    assert [t.category for t in f1] == ["T", "I", "D"]
    assert all(t.crosses == ("SandPay network",) for t in f1)
    assert all(t.crosses == () for t in threats if t.element_id in ("portal", "db", "merchant"))


def test_draft_dfd_has_a_magic_sink():
    assert check_dfd(sandpay_dfd(with_log_review=False)) == ["never-read: log"]
    assert check_dfd(sandpay_dfd()) == []


def test_check_dfd_rules():
    dfd = Dfd([
        Element("u", "User", "interactor"),
        Element("p", "App", "process"),
        Element("s", "Store", "data_store"),
        Element("x", "Thing", "server"),
        Element("a", "User straight to disk", "data_flow", "u", "s"),
        Element("b", "To nowhere", "data_flow", "p", "missing"),
        Element("c", "From a flow", "data_flow", "a", "p"),
        Element("d", "App writes", "data_flow", "p", "s"),
    ], [Boundary("B", frozenset({"p", "s"}))])
    assert check_dfd(dfd) == ["unknown-kind: x", "no-process: a", "bad-endpoint: b", "bad-endpoint: c", "never-read: s"]


def test_check_register():
    register = [
        {"id": "T1", "category": "S", "response": "mitigate", "requirement": "Reject unsigned tokens",
         "test": "probe: unsigned token gets 401"},
        {"id": "T2", "category": "E", "response": "mitigate", "requirement": "Allow-list profile fields"},
        {"id": "T3", "category": "D", "response": "accept", "reason": "Lockout is rate-limited per account"},
        {"id": "T4", "category": "I", "response": "transfer"},
        {"id": "T5", "category": "X", "response": "eliminate"},
        {"id": "T6", "category": "R"},
        {"id": "T7", "category": "T", "response": "accept", "reason": "Internal only", "owner": "Head of payments"},
        {"id": "T8", "category": "T", "response": "transfer", "owner": "Hosting provider (contract 7)"},
        {"id": "T9", "category": "I", "response": "mitigate", "requirement": "  ", "test": "x"},
    ]
    assert check_register(register) == [
        "no-test: T2",
        "no-owner: T3",
        "no-owner: T4",
        "bad-category: T5",
        "no-response: T6",
        "no-requirement: T9",
    ]
