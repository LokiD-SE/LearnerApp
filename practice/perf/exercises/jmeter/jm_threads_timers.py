"""Exercise - which timers apply to a sampler, and how long do they make a thread pause?

From the JMeter user manual ("Elements of a Test Plan", 3.4 Timers and 3.10 Scoping Rules) and the Component
Reference (18.6 Timers):

- "A timer will cause JMeter to delay a certain amount of time before each sampler which is in its scope."
- "If you choose to add more than one timer to a Thread Group, JMeter takes the sum of the timers and pauses for
  that amount of time before executing the samplers to which the timers apply."
- Timers are hierarchical: a timer applies to the samplers below its parent - its parent sampler only, or every
  sampler under its parent controller or thread group, wherever the timer sits among its siblings.
- Constant Timer: "Number of milliseconds to pause."
- Uniform Random Timer: "The total delay is the sum of the random value and the offset value", the random value
  being up to "Random Delay Maximum".
- Gaussian Random Timer: "The total delay is the sum of the Gaussian distributed value (with mean 0.0 and standard
  deviation 1.0) times the deviation value you specify, and the offset value."

A test plan here is a tree of dicts: ``{"type": ..., "name": ..., "children": [...]}`` plus the timer's settings:
``ConstantTimer`` (``delay_ms``), ``UniformRandomTimer`` (``offset_ms``, ``range_ms``), ``GaussianRandomTimer``
(``offset_ms``, ``deviation_ms``). Samplers have ``"type": "Sampler"``; anything else with children is a
container (Thread Group, controller).
"""

from __future__ import annotations

TIMER_TYPES = ("ConstantTimer", "UniformRandomTimer", "GaussianRandomTimer")


def timers_in_scope(plan: dict, sampler: str) -> list[dict]:
    """The timers that run before ``sampler``: timer children of the sampler and of each of its ancestors."""
    raise NotImplementedError("TODO: timers_in_scope")


def expected_delay_ms(plan: dict, sampler: str) -> float:
    """The mean pause before ``sampler``: the sum of the means of every timer in its scope."""
    raise NotImplementedError("TODO: expected_delay_ms")


def delay_bounds_ms(plan: dict, sampler: str) -> tuple[float, float] | None:
    """(shortest, longest) pause before ``sampler``, or None when a Gaussian timer makes it unbounded."""
    raise NotImplementedError("TODO: delay_bounds_ms")


def samplers(plan: dict) -> list[str]:
    """Sampler names in tree order - the order a thread runs them in (no logic controllers that reorder)."""
    raise NotImplementedError("TODO: samplers")


def iteration_ms(plan: dict, response_ms: dict[str, float]) -> float:
    """Mean time for one thread to run every sampler once: each sampler's timers plus its response time."""
    raise NotImplementedError("TODO: iteration_ms")


def throughput_per_minute(plan: dict, response_ms: dict[str, float], threads: int) -> float:
    """Samples per minute that ``threads`` closed-loop threads produce at those response times."""
    raise NotImplementedError("TODO: throughput_per_minute")
