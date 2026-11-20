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

# Exact test classes that the name rules below would get wrong or miss (real JMeter 5.6.3 class names).
EXACT = {
    "TestPlan": "test-plan",
    "ThreadGroup": "thread-group",
    "SetupThreadGroup": "thread-group",
    "PostThreadGroup": "thread-group",
    "OpenModelThreadGroup": "thread-group",
    "ConfigTestElement": "config",  # HTTP Request Defaults and other "defaults" elements
    "Arguments": "config",  # User Defined Variables
    "CSVDataSet": "config",
    "ResultCollector": "listener",  # View Results Tree, Summary Report, Aggregate Report, ...
    "BackendListener": "listener",
    "Summariser": "listener",
}
# Otherwise the first matching suffix wins.
SUFFIXES = (
    ("SamplerProxy", "sampler"),
    ("Sampler", "sampler"),
    ("Controller", "controller"),
    ("PreProcessor", "pre"),
    ("PostProcessor", "post"),
    ("Extractor", "post"),  # RegexExtractor, BoundaryExtractor, XPathExtractor
    ("Timer", "timer"),
    ("Assertion", "assertion"),
    ("Manager", "config"),  # CookieManager, HeaderManager, AuthManager, CacheManager
    ("DataSet", "config"),
    ("Config", "config"),  # CounterConfig, RandomVariableConfig
)


@dataclass
class Node:
    kind: str
    testclass: str
    name: str
    enabled: bool = True
    children: list["Node"] = field(default_factory=list)


def classify(testclass: str) -> str:
    """The kind of element for a JMeter test class: one of test-plan, thread-group, sampler, controller,
    config, pre, timer, post, assertion, listener - or "other" if no rule matches."""
    if testclass in EXACT:
        return EXACT[testclass]
    for suffix, kind in SUFFIXES:
        if testclass.endswith(suffix):
            return kind
    return "other"


def _children(hash_tree: ET.Element) -> list[Node]:
    items = list(hash_tree)
    nodes = []
    for i in range(0, len(items), 2):
        element = items[i]
        if element.tag == "hashTree":
            raise ValueError("a hashTree without an element before it - the pairs are out of step")
        sub = items[i + 1] if i + 1 < len(items) else None
        if sub is None or sub.tag != "hashTree":
            raise ValueError(f"element {element.get('testname')!r} has no hashTree after it")
        testclass = element.get("testclass", element.tag)
        nodes.append(Node(classify(testclass), testclass, element.get("testname", ""),
                          element.get("enabled", "true") != "false", _children(sub)))
    return nodes


def parse_jmx(path: str | Path) -> Node:
    """The Test Plan node with its whole tree. Raises ValueError if the file is not a test plan."""
    root = ET.parse(path).getroot()
    if root.tag != "jmeterTestPlan":
        raise ValueError(f"not a JMeter test plan: root element is <{root.tag}>")
    top = root.find("hashTree")
    if top is None:
        raise ValueError("no top-level hashTree")
    nodes = _children(top)
    if len(nodes) != 1 or nodes[0].kind != "test-plan":
        raise ValueError("the top-level hashTree must hold exactly one TestPlan")
    return nodes[0]


def scope(plan: Node) -> dict[str, dict[str, list[str]]]:
    """For every enabled sampler (by name), the names of the enabled hierarchical elements that apply to it,
    by kind. Within a kind the names are listed from the outermost level to the sampler's own children, in
    tree order within a level - a listing convention, not the run order. A disabled element, and everything
    under a disabled controller, does not take part."""
    result: dict[str, dict[str, list[str]]] = {}

    def walk(node: Node, inherited: dict[str, list[str]]) -> None:
        here = {k: list(v) for k, v in inherited.items()}
        for child in node.children:
            if child.enabled and child.kind in HIERARCHICAL:
                here[child.kind].append(child.name)
        for child in node.children:
            if not child.enabled:
                continue
            if child.kind == "sampler":
                own = {k: list(v) for k, v in here.items()}
                for grandchild in child.children:
                    if grandchild.enabled and grandchild.kind in HIERARCHICAL:
                        own[grandchild.kind].append(grandchild.name)
                result[child.name] = own
            elif child.kind in ("thread-group", "controller"):
                walk(child, here)

    walk(plan, {k: [] for k in HIERARCHICAL})
    return result
