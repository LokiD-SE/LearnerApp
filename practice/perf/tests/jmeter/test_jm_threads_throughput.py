"""Exercise: hold a target rate with a Constant Throughput Timer (jmeter/jm_threads_throughput.jmx).

The structure test reads the plan; the run test executes it with real JMeter against the practice API and measures
the rate over the time the samples actually ran - not over the nominal duration, which includes JVM start-up.
"""

import xml.etree.ElementTree as ET

import pytest
from load_tools import jmeter_home, practice_file, read_jtl, run_jmeter
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

PLAN = practice_file("jmeter/jm_threads_throughput.jmx")
GROUP_WIDE_MODES = {"2", "4"}  # all active threads in current thread group (2), and its shared variant (4)


def thread_group_children(root: ET.Element) -> ET.Element:
    """The hashTree holding the Thread Group's children (in a .jmx, an element's children follow it in a hashTree)."""
    for tree in root.iter("hashTree"):
        items = list(tree)
        for i, el in enumerate(items):
            if el.tag == "ThreadGroup":
                return items[i + 1]
    raise AssertionError("no ThreadGroup in the plan")


def timers(root: ET.Element) -> list[ET.Element]:
    return [t for t in thread_group_children(root).iter("ConstantThroughputTimer") if t.get("enabled", "true") == "true"]


def prop(el: ET.Element, name: str) -> str:
    for child in el:
        if child.get("name") == name:
            return (child.text or "").strip()
    raise AssertionError(f"{el.tag} has no property {name!r}")


def test_plan_has_one_group_wide_constant_throughput_timer():
    found = timers(ET.parse(PLAN).getroot())
    assert len(found) == 1, f"expected one enabled Constant Throughput Timer in the Thread Group, found {len(found)}"
    timer = found[0]
    assert "__P(per_minute" in prop(timer, "throughput"), "read the target from the per_minute property, not a literal"
    assert prop(timer, "calcMode") in GROUP_WIDE_MODES, (
        "calcMode must divide the target among the group's active threads; 'this thread only' (0) "
        "makes every thread hold the full target")


@pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")
def test_real_run_holds_the_target_rate(tmp_path):
    threads, per_minute = 4, 900  # 15 samples per second for the whole group - not the plan's default of 600
    with serve(TargetConfig(latency_ms=1)) as base:
        props = {"port": base.rsplit(":", 1)[1], "threads": threads, "per_minute": per_minute, "duration": 5}
        data = read_jtl(run_jmeter(PLAN, props, tmp_path))
    assert all(r["responseCode"] == "200" for r in data)
    stamps = sorted(int(r["timeStamp"]) for r in data)
    span_s = (stamps[-1] - stamps[0]) / 1000
    # every thread's first sample opens the span, so `threads` samples are fence posts, not intervals
    rate = (len(data) - threads) / span_s
    target = per_minute / 60
    assert 0.7 * target <= rate <= 1.3 * target, f"{rate:.1f} samples/s, target {target:.1f}/s ({len(data)} samples)"
