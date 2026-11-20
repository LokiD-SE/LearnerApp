"""Exercise: predict JMeter's execution order (exercises/jmeter/jm_arch_order.py).

Two tests compare your prediction with the manual's own example; two run real JMeter 5.6.3 plans whose
elements log their names, and compare with what JMeter actually did."""

import pytest
from jm_arch_fixture import build_plan, run_order
from jmeter.jm_arch_order import predict_order
from load_tools import jmeter_home

pytestmark = pytest.mark.exercise

# JMeter user manual, 3.9 Execution order - the example tree under one controller.
MANUAL = [("thread-group", "TG", [("controller", "Controller", [
    ("post", "Post-Processor 1"), ("sampler", "Sampler 1"), ("sampler", "Sampler 2"), ("timer", "Timer 1"),
    ("assertion", "Assertion 1"), ("pre", "Pre-Processor 1"), ("timer", "Timer 2"), ("post", "Post-Processor 2"),
])])]
MANUAL_ORDER = [
    "Pre-Processor 1", "Timer 1", "Timer 2", "Sampler 1", "Post-Processor 1", "Post-Processor 2", "Assertion 1",
    "Pre-Processor 1", "Timer 1", "Timer 2", "Sampler 2", "Post-Processor 1", "Post-Processor 2", "Assertion 1",
]

NESTED = [("thread-group", "TG", [
    ("pre", "Pre TG"), ("timer", "Timer TG"), ("post", "Post TG"), ("assertion", "Assert TG"),
    ("controller", "C", [
        ("pre", "Pre C"), ("timer", "Timer C"), ("post", "Post C"), ("assertion", "Assert C"),
        ("sampler", "S1", [("pre", "Pre S1"), ("timer", "Timer S1"), ("post", "Post S1"), ("assertion", "Assert S1")]),
    ]),
    ("sampler", "S2"),
])]

SHOP = [("thread-group", "Merchants", [
    ("timer", "Think time"),
    ("controller", "Sign in", [("sampler", "POST /auth/token", [("post", "Extract token")])]),
    ("controller", "Browse", [
        ("pre", "Pick payment id"),
        ("sampler", "GET /v1/payments", [("assertion", "Status is 200")]),
        ("sampler", "GET /v1/payments/{id}"),
        ("timer", "Read the payment"),
    ]),
    ("controller", "Nothing to time", [("timer", "Orphan timer"), ("assertion", "Orphan assertion")]),
])]


def test_manual_example():
    assert predict_order(MANUAL) == MANUAL_ORDER


def test_elements_without_a_sampler_never_run():
    order = predict_order(SHOP)
    assert "Orphan timer" not in order and "Orphan assertion" not in order


def test_nested_levels_by_hand():
    assert predict_order(NESTED) == [
        "Pre TG", "Pre C", "Pre S1", "Timer S1", "Timer C", "Timer TG", "S1",
        "Post TG", "Post C", "Post S1", "Assert TG", "Assert C", "Assert S1",
        "Pre TG", "Timer TG", "S2", "Post TG", "Assert TG",
    ]


def test_refuses_elements_directly_under_the_test_plan():
    with pytest.raises(ValueError):
        predict_order([("pre", "Pre Plan")] + NESTED)


@pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")
@pytest.mark.parametrize("tree", [NESTED, SHOP], ids=["nested", "shop"])
def test_matches_a_real_jmeter_run(tree, tmp_path):
    assert predict_order(tree) == run_order(build_plan(tree), tmp_path)
