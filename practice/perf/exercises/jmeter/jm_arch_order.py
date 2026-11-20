"""Predict the order in which JMeter runs the elements of a simple test plan.

The tree is written as nested tuples, the same shape as ``support/jm_arch_fixture.py`` uses: ``(kind, name)``
for a leaf, ``(kind, name, [children])`` otherwise. Kinds: thread-group, controller (Simple Controller),
sampler, pre, timer, post, assertion. One thread group, one thread, one iteration.

The rule for elements at ONE level is documented (JMeter user manual, 3.9 Execution order):

    Configuration elements, Pre-Processors, Timers, Sampler,
    Post-Processors (unless SampleResult is null), Assertions (unless SampleResult is null),
    Listeners (unless SampleResult is null)

"Within a type, elements are processed in the order in which they appear in the tree", and timers,
assertions, pre- and post-processors "are only processed if there is a sampler to which they apply".

Across levels (thread group, controller, the sampler's own children) the manual says nothing. JMeter 5.6.3, run
with this lesson's fixture, ran pre-processors, post-processors and assertions from the OUTERMOST level inwards,
and timers from the INNERMOST level outwards. ``predict_order`` follows that observation; elements placed
directly under the Test Plan behave differently again, so this function refuses them.
"""

from __future__ import annotations

HIERARCHICAL = ("pre", "timer", "post", "assertion")


def _parts(node: tuple) -> tuple[str, str, list[tuple]]:
    return node[0], node[1], (node[2] if len(node) > 2 else [])


def predict_order(tree: list[tuple]) -> list[str]:
    """The element names in the order JMeter runs them, for a tree with exactly one thread group at the top
    and no pre-processors, timers, post-processors or assertions directly under the Test Plan (raise
    ValueError otherwise).

    TODO. Walk the samplers in tree order (descending into controllers). For each sampler, the "levels" in
    scope are: the thread group's children, each enclosing controller's children, the sampler's own children.
    Emit: pre-processors (outermost level first), timers (innermost level first), the sampler, post-processors
    and assertions (outermost first); within one level, in tree order.
    """
    raise NotImplementedError("predict_order")
