"""Apdex per the Apdex specification v1.1 and JMeter's dashboard, checked by hand and against a real run."""

import pytest
from fundamentals.metrics_apdex import apdex, apdex_by_label, classify, rating, uniform_output
from load_tools import jmeter_home
from metrics_fixture import APDEX_F_MS, APDEX_T_MS, jmeter_quotes_run

pytestmark = pytest.mark.exercise


def test_zones_include_their_upper_threshold():
    assert classify(500, True, 500, 1500) == "satisfied"
    assert classify(501, True, 500, 1500) == "tolerating"
    assert classify(1500, True, 500, 1500) == "tolerating"
    assert classify(1501, True, 500, 1500) == "frustrated"


def test_a_failed_sample_is_frustrated_however_fast():
    assert classify(3, False, 500, 1500) == "frustrated"


def test_the_specification_example():
    # Apdex spec 4.1: 80 % satisfied, 10 % tolerating, 10 % frustrated -> 0.85
    samples = [(100, True)] * 80 + [(900, True)] * 10 + [(5000, True)] * 10
    assert apdex(samples, 500, 2000) == pytest.approx(0.85)


def test_defaults_are_jmeters_500_and_1500():
    assert apdex([(1400, True), (400, True)]) == pytest.approx(0.75)
    assert apdex([(1600, True), (400, True)]) == pytest.approx(0.5)


def test_bad_input():
    with pytest.raises(ValueError):
        apdex([])
    with pytest.raises(ValueError):
        apdex([(1, True)], t_ms=600, f_ms=500)


def test_uniform_output_and_rating():
    assert uniform_output(0.855, 120, 4) == "0.86 [4.0]"  # arithmetic rounding, T shown in seconds
    assert uniform_output(0.9951, 500, 0.5) == "1.00 [0.5]"
    assert uniform_output(0.8, 40, 4) == "0.80 [4.0]*"  # small group: 1 to 99 samples
    assert uniform_output(None, 0, 4) == "NS [4.0]"
    assert uniform_output(0.77, 300, 450) == "0.77 [450]"
    with pytest.raises(ValueError):
        uniform_output(0.9, 200, 0.025)  # 25 ms is finer than the specification allows
    assert [rating(s) for s in (0.995, 0.935, 0.85, 0.7, 0.5, 0.494)] == [
        "Excellent", "Excellent", "Good", "Fair", "Poor", "Unacceptable"]


@pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")
def test_matches_jmeter_dashboard_for_a_real_run():
    run = jmeter_quotes_run()
    mine = apdex_by_label(run["rows"], APDEX_T_MS, APDEX_F_MS)
    assert mine == pytest.approx(run["apdex"])
    assert mine["GET quote (pricing down)"] == 0.0  # 3 ms answers, all failed
