"""Read a JMeter .jmx file as a tree and work out which elements apply to which sampler.

A .jmx file is XML. Every element is followed by a ``<hashTree>`` that holds its children, so inside any
``<hashTree>`` the children come in pairs: element, hashTree, element, hashTree, ... An element with no
children still gets an empty ``<hashTree/>``.

Scoping (JMeter user manual, "Elements of a Test Plan", 3.10 Scoping Rules): controllers and samplers are
*ordered*; listeners, config elements, pre-processors, post-processors, assertions and timers are
*hierarchical* - one applies to the sampler it is a child of, or to every sampler below the controller,
thread group or test plan it is a child of. Order among siblings is irrelevant for hierarchical elements.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

HIERARCHICAL = ("config", "pre", "timer", "post", "assertion", "listener")

@dataclass
class Node:
    kind: str
    testclass: str
    name: str
    enabled: bool = True
    children: list["Node"] = field(default_factory=list)


def classify(testclass: str) -> str:
    """The kind of element for a JMeter test class: one of test-plan, thread-group, sampler, controller,
    config, pre, timer, post, assertion, listener - or "other" if no rule matches.

    TODO. Real JMeter 5.6.3 class names follow patterns, with a few exceptions:
    - exact names: TestPlan; ThreadGroup, SetupThreadGroup, PostThreadGroup, OpenModelThreadGroup;
      ConfigTestElement (HTTP Request Defaults), Arguments (User Defined Variables) and CSVDataSet are config;
      ResultCollector (View Results Tree, Summary Report...), BackendListener and Summariser are listeners;
    - otherwise by suffix: ...Sampler / ...SamplerProxy, ...Controller, ...PreProcessor,
      ...PostProcessor or ...Extractor, ...Timer, ...Assertion, ...Manager / ...DataSet / ...Config (config).
    """
    raise NotImplementedError("classify")


def parse_jmx(path: str | Path) -> Node:
    """The Test Plan node with its whole tree. Raises ValueError if the file is not a test plan.

    TODO. The root element is <jmeterTestPlan>; its <hashTree> holds exactly one TestPlan and that
    TestPlan's <hashTree>. Inside every <hashTree> the children come in pairs (element, hashTree): pair them,
    raise ValueError when a pair is out of step, and build a Node for each element (kind from classify on
    its testclass attribute, name from testname, enabled unless enabled="false").
    """
    raise NotImplementedError("parse_jmx")


def scope(plan: Node) -> dict[str, dict[str, list[str]]]:
    """For every enabled sampler (by name), the names of the enabled hierarchical elements that apply to it,
    by kind (keys: config, pre, timer, post, assertion, listener - every key present, lists may be empty).
    Within a kind list the names from the outermost level to the sampler's own children, in tree order within
    a level - a listing convention, not the run order. A disabled element, and everything under a disabled
    controller, does not take part.

    TODO. A hierarchical element applies to its parent sampler, or to every sampler below its parent
    controller, thread group or test plan - wherever it sits among its siblings.
    """
    raise NotImplementedError("scope")
