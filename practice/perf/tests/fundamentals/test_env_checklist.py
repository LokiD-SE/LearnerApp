import pytest
from fundamentals.env_checklist import CHECKS, check_run_plan

pytestmark = pytest.mark.exercise


def good_plan(**changes):
    plan = {
        "tool": "jmeter", "gui": False, "listeners": ["Summary Report"], "target_host": "perf.sandpay.example",
        "approved_hosts": ["perf.sandpay.example"], "generator_cores": 8, "processes": 1, "expected_rps": 300,
        "rps_per_process": 1000, "virtual_users": 200, "unique_data_rows": 500, "warmup_s": 300,
        "duration_s": 2100, "min_steady_s": 1800, "state_reset": True, "generator_monitored": True,
    }
    plan.update(changes)
    return plan


def test_a_good_plan_has_no_problems():
    assert check_run_plan(good_plan()) == []


@pytest.mark.parametrize("changes, code", [
    ({"target_host": "api.sandpay.example"}, "scope"),
    ({"gui": True}, "cli-mode"),
    ({"listeners": ["Summary Report", "View Results Tree"]}, "heavy-listeners"),
    ({"listeners": ["View Results in Table"]}, "heavy-listeners"),
    ({"tool": "locust", "listeners": [], "processes": 12, "rps_per_process": 4000}, "too-many-processes"),
    ({"expected_rps": 900}, "generator-capacity"),
    ({"unique_data_rows": 150}, "data-volume"),
    ({"warmup_s": 0, "duration_s": 1800}, "no-warm-up"),
    ({"duration_s": 1500}, "steady-state-too-short"),
    ({"state_reset": False}, "state-not-reset"),
    ({"generator_monitored": False}, "generator-not-monitored"),
])
def test_each_problem_is_found_alone(changes, code):
    assert check_run_plan(good_plan(**changes)) == [code]


def test_headroom_boundary():
    # 800 is exactly 80 % of one process's 1000 rps: allowed; 801 is not.
    assert check_run_plan(good_plan(expected_rps=800)) == []
    assert check_run_plan(good_plan(expected_rps=801)) == ["generator-capacity"]


def test_listeners_only_matter_for_jmeter():
    plan = good_plan(tool="locust", listeners=["View Results Tree"], processes=4, rps_per_process=1000)
    assert check_run_plan(plan) == []


def test_capacity_scales_with_processes():
    plan = good_plan(tool="locust", listeners=[], processes=4, rps_per_process=1000, expected_rps=3000)
    assert check_run_plan(plan) == []


def test_problems_come_in_check_order():
    plan = good_plan(generator_monitored=False, gui=True, target_host="prod.sandpay.example", warmup_s=0)
    found = check_run_plan(plan)
    assert found == sorted(found, key=CHECKS.index)
    assert found == ["scope", "cli-mode", "no-warm-up", "generator-not-monitored"]
