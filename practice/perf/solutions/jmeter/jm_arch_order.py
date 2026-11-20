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
    and no pre-processors, timers, post-processors or assertions directly under the Test Plan."""
    groups = [n for n in tree if n[0] == "thread-group"]
    if len(groups) != 1 or len(tree) != 1:
        raise ValueError("expected exactly one thread group and nothing else under the Test Plan")
    order: list[str] = []

    def own(children: list[tuple], kind: str) -> list[str]:
        return [_parts(c)[1] for c in children if c[0] == kind]

    def walk(children: list[tuple], levels: list[list[tuple]]) -> None:
        levels = levels + [children]
        for child in children:
            kind, name, grandchildren = _parts(child)
            if kind == "sampler":
                scope = levels + [grandchildren]
                order.extend(n for level in scope for n in own(level, "pre"))
                order.extend(n for level in reversed(scope) for n in own(level, "timer"))
                order.append(name)
                for k in ("post", "assertion"):
                    order.extend(n for level in scope for n in own(level, k))
            elif kind == "controller":
                walk(grandchildren, levels)
            elif kind not in HIERARCHICAL:
                raise ValueError(f"unsupported kind {kind!r}")

    walk(_parts(groups[0])[2], [])
    return order
