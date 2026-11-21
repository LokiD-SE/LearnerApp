"""Checks exercises/devsecops/cicd_plan.py: where each security check runs in the pipeline."""

import pytest
from cicd_fixture import CHECKS, TRIGGERS, Check, Trigger
from devsecops.cicd_plan import place, plan

pytestmark = pytest.mark.exercise

BY_NAME = {c.name: c for c in CHECKS}


@pytest.mark.parametrize(
    ("name", "trigger"),
    [
        ("secret-scan-staged", "pre-commit"),  # 5 s: fits the hook
        ("sast-changed-files", "pull-request"),  # 90 s: too slow for the hook
        ("secret-scan-history", "pull-request"),  # 400 s: fits the pull-request budget of 600
        ("sast-full", "merge"),  # 1500 s: over the pull-request budget, no app needed
        ("zap-baseline", "merge"),  # 900 s and needs a deployed app, which only merge and nightly have
        ("zap-full-active", "nightly"),  # 7200 s: over the merge budget of 3600
    ],
)
def test_each_check_goes_to_the_earliest_trigger_that_fits(name, trigger):
    assert place(BY_NAME[name]).name == trigger


def test_a_check_that_needs_credentials_is_never_placed_where_code_is_untrusted():
    assert place(Check("sign", "sca", 5, needs_secrets=True)).name == "merge"
    assert place(BY_NAME["sbom-and-sign"]).name == "merge"
    assert place(BY_NAME["zap-authenticated"]).name == "merge"


def test_a_check_that_needs_an_app_waits_for_a_deployed_environment():
    assert place(Check("probe", "dast", 5, needs_app=True)).name == "merge"


def test_the_budget_is_inclusive():
    assert place(Check("edge", "sast", 15)).name == "pre-commit"
    assert place(Check("edge", "sast", 16)).name == "pull-request"
    assert place(Check("edge", "sast", 600)).name == "pull-request"
    assert place(Check("edge", "sast", 601)).name == "merge"


def test_a_check_that_fits_nowhere_is_an_error_that_names_it():
    with pytest.raises(ValueError, match="endless-scan"):
        place(Check("endless-scan", "dast", 40000, needs_app=True))
    with pytest.raises(ValueError, match="secret-wait"):
        place(Check("secret-wait", "sca", 5, needs_secrets=True), triggers=TRIGGERS[:2])


def test_plan_lists_every_trigger_in_order_with_sorted_names():
    result = plan(CHECKS)
    assert list(result) == ["pre-commit", "pull-request", "merge", "nightly"]
    assert result == {
        "pre-commit": ["secret-scan-staged"],
        "pull-request": ["sast-changed-files", "sca-lockfile-audit", "secret-scan-history", "secret-scan-staged"],
        "merge": ["sast-full", "sbom-and-sign", "zap-authenticated", "zap-baseline"],
        "nightly": ["zap-full-active"],
    }


def test_the_hook_is_not_the_control_so_hook_checks_repeat_in_the_pull_request_stage():
    result = plan([Check("a-hook-check", "secrets", 3), Check("b-slow-check", "sast", 100)])
    assert result["pre-commit"] == ["a-hook-check"]
    assert result["pull-request"] == ["a-hook-check", "b-slow-check"]
    # nothing else is repeated
    assert sum(len(v) for v in plan(CHECKS).values()) == len(CHECKS) + 1


def test_an_empty_plan_still_has_every_trigger():
    assert plan([]) == {"pre-commit": [], "pull-request": [], "merge": [], "nightly": []}


def test_plan_accepts_other_triggers():
    custom = (Trigger("local", 10, False, False), Trigger("ci", 100, True, True))
    result = plan([Check("quick", "secrets", 2), Check("deep", "dast", 90, needs_app=True)], custom)
    assert result == {"local": ["quick"], "ci": ["deep", "quick"]}


def test_plan_does_not_mutate_or_depend_on_input_order():
    shuffled = list(reversed(CHECKS))
    assert plan(shuffled) == plan(CHECKS)
    assert [c.name for c in CHECKS][0] == "secret-scan-staged"
