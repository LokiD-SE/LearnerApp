"""jm_groovy_ exercise 3: exercises/jmeter/jm_groovy_cost.py turns a recorded JTL into a scripting cost.

The JTL is a fixture recorded once with real JMeter (tests/jmeter/fixtures/jm_groovy_cost.jmx), so the numbers
are exact here; on your machine a fresh run gives different milliseconds and the same shape.
"""

from pathlib import Path

import pytest
from load_tools import read_jtl

from jmeter.jm_groovy_cost import compile_overhead_ms, generator_cores, nearest_rank, summarise

pytestmark = pytest.mark.exercise

JTL = Path(__file__).parent / "fixtures" / "jm_groovy_cost.jtl"
CACHED, UNCACHED, BSH = "hmac groovy cached", "hmac groovy uncached", "hmac beanshell"


@pytest.fixture(scope="module")
def summary():
    return summarise(read_jtl(JTL))


def test_nearest_rank():
    assert nearest_rank(list(range(1, 101)), 95) == 95
    assert nearest_rank([5, 1, 3], 50) == 3
    assert nearest_rank([7], 99) == 7
    assert nearest_rank([4, 2], 1) == 2


def test_summary_has_every_label_with_all_samples(summary):
    assert set(summary) == {CACHED, UNCACHED, BSH}
    assert {label: s["n"] for label, s in summary.items()} == {CACHED: 200, UNCACHED: 200, BSH: 200}


def test_first_sample_is_kept_apart(summary):
    # The first cached Groovy sample pays for starting the Groovy engine and compiling: almost a second.
    assert summary[CACHED]["first_ms"] == 951
    assert summary[CACHED]["median_ms"] == 1 and summary[CACHED]["p95_ms"] == 2


def test_steady_state_and_totals(summary):
    assert (summary[UNCACHED]["median_ms"], summary[UNCACHED]["p95_ms"], summary[UNCACHED]["total_ms"]) == (21, 29, 4301)
    assert (summary[BSH]["median_ms"], summary[BSH]["p95_ms"], summary[BSH]["total_ms"]) == (3, 5, 735)
    assert summary[CACHED]["total_ms"] == 1168


def test_compile_overhead(summary):
    assert compile_overhead_ms(summary, CACHED, UNCACHED) == 20


def test_generator_cores():
    assert generator_cores(21, 200) == 4.2
    assert generator_cores(1, 200) == 0.2
    assert generator_cores(2.5, 40) == 0.1
