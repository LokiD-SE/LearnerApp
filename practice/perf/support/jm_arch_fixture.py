"""Fixture for the lesson "JMeter architecture and test plans" (jm_arch_ exercises).

Builds small JMeter 5.6.3 test plans in which every element announces itself, runs them in CLI mode and reads
back the order in which JMeter ran the elements. Each pre-processor, post-processor, timer, assertion and
sampler is a JSR223 element (Groovy, bundled with JMeter) whose script writes ``ORDER <name>`` to the run log
(``jmeter.log``, set with ``-j``). Nothing is sent over the network.

A tree is written as nested tuples: ``(kind, name)`` for a leaf, or ``(kind, name, [children])``. Kinds:
``thread-group``, ``controller`` (Simple Controller), ``sampler``, ``pre``, ``post``, ``timer``, ``assertion``.

    plan = build_plan([("thread-group", "TG", [("controller", "C", [("sampler", "S1"), ("timer", "T1")])])])
    order = run_order(plan, tmp_path)   # ["T1", "S1"]
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.sax.saxutils import escape

from load_tools import run_jmeter

JSR223 = {
    "sampler": ("JSR223Sampler", "SampleResult.setSuccessful(true); SampleResult.setResponseCodeOK(); "),
    "pre": ("JSR223PreProcessor", ""),
    "post": ("JSR223PostProcessor", ""),
    "assertion": ("JSR223Assertion", ""),
    "timer": ("JSR223Timer", ""),
}


def _jsr223(kind: str, name: str) -> str:
    testclass, extra = JSR223[kind]
    script = f'log.info("ORDER {name}"); {extra}'
    if kind == "timer":
        script += "return 0;"  # a JSR223 Timer's script returns the delay in milliseconds
    return (
        f'<{testclass} guiclass="TestBeanGUI" testclass="{testclass}" testname="{escape(name)}" enabled="true">'
        f'<stringProp name="scriptLanguage">groovy</stringProp>'
        f'<stringProp name="parameters"></stringProp><stringProp name="filename"></stringProp>'
        f'<stringProp name="cacheKey">true</stringProp>'
        f"<stringProp name=\"script\">{escape(script)}</stringProp></{testclass}>"
    )


def _element(node: tuple) -> str:
    kind, name = node[0], node[1]
    children = node[2] if len(node) > 2 else []
    if kind == "thread-group":
        head = (
            f'<ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="{escape(name)}" enabled="true">'
            '<stringProp name="ThreadGroup.num_threads">1</stringProp>'
            '<stringProp name="ThreadGroup.ramp_time">0</stringProp>'
            '<stringProp name="ThreadGroup.on_sample_error">continue</stringProp>'
            '<elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" '
            'testclass="LoopController"><stringProp name="LoopController.loops">1</stringProp>'
            '<boolProp name="LoopController.continue_forever">false</boolProp></elementProp></ThreadGroup>'
        )
    elif kind == "controller":
        head = (f'<GenericController guiclass="LogicControllerGui" testclass="GenericController" '
                f'testname="{escape(name)}" enabled="true"/>')
    else:
        head = _jsr223(kind, name)
    return head + "<hashTree>" + "".join(_element(c) for c in children) + "</hashTree>"


def build_plan(tree: list[tuple]) -> str:
    """A complete .jmx document: a Test Plan whose children are ``tree``."""
    body = "".join(_element(n) for n in tree)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3"><hashTree>'
        '<TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="Order probe" enabled="true">'
        '<elementProp name="TestPlan.user_defined_variables" elementType="Arguments" guiclass="ArgumentsPanel" '
        'testclass="Arguments"><collectionProp name="Arguments.arguments"/></elementProp></TestPlan>'
        f"<hashTree>{body}</hashTree></hashTree></jmeterTestPlan>\n"
    )


def run_order(plan_xml: str, out_dir: Path) -> list[str]:
    """Runs the plan in CLI mode and returns the element names in the order JMeter ran them."""
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = out_dir / "order.jmx"
    plan.write_text(plan_xml)
    run_jmeter(plan, {}, out_dir)
    log = (out_dir / "jmeter.log").read_text()
    return re.findall(r"ORDER (.+?)\s*$", log, flags=re.M)
