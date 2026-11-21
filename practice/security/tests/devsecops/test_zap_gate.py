"""Checks exercises/devsecops/zap_gate.py: the rule config, the baseline verdict and the exitStatus job."""

import pytest
from devsecops.zap_gate import evaluate, exit_status, parse_rule_config, plugin_id
from zap_fixture import BASELINE_CONFIG, Finding

pytestmark = pytest.mark.exercise


def f(rule_id, risk="Low"):
    return Finding(rule_id, "name " + rule_id, risk, "http://127.0.0.1:9/" + rule_id)


FINDINGS = [f("10010"), f("10011"), f("10011"), f("10021"), f("10036-2"), f("10038-1", "Medium"), f("90022", "Medium")]


def test_plugin_id_drops_the_alert_type():
    assert plugin_id("10038-1") == "10038"
    assert plugin_id("10021") == "10021"
    assert plugin_id("6-1") == "6"


def test_parse_reads_actions_and_messages_and_skips_comments():
    config = parse_rule_config(BASELINE_CONFIG)
    assert config == {
        "10010": ("WARN", ""),
        "10011": ("FAIL", "session cookies must be Secure"),
        "10021": ("IGNORE", ""),
        "10036": ("INFO", ""),
        "10038": ("WARN", ""),
    }


def test_parse_is_forgiving_about_case_and_blank_lines_and_strict_about_typos():
    assert parse_rule_config("\n\n  # c\n10010\tfail\n") == {"10010": ("FAIL", "")}
    with pytest.raises(ValueError):
        parse_rule_config("10010\tFAILL\n")
    with pytest.raises(ValueError):
        parse_rule_config("10010 WARN\n")


def test_evaluate_counts_rules_not_alerts_and_fails_the_pipeline():
    result = evaluate(FINDINGS, parse_rule_config(BASELINE_CONFIG))
    assert result.outcomes == {
        "10010": "WARN", "10011": "FAIL", "10021": "IGNORE", "10036": "INFO", "10038": "WARN", "90022": "WARN",
    }
    assert result.counts == {"FAIL": 1, "WARN": 3, "INFO": 1, "IGNORE": 1}
    assert result.exit_code == 1


def test_warn_only_exits_2_and_info_or_ignore_exit_0():
    config = parse_rule_config(BASELINE_CONFIG)
    no_fail = [x for x in FINDINGS if x.rule_id != "10011"]
    assert evaluate(no_fail, config).exit_code == 2
    quiet = [f("10021"), f("10036-2")]
    result = evaluate(quiet, config)
    assert result.exit_code == 0
    assert result.counts == {"FAIL": 0, "WARN": 0, "INFO": 1, "IGNORE": 1}
    assert evaluate([], config).exit_code == 0


def test_rules_missing_from_the_config_use_the_default():
    config = parse_rule_config(BASELINE_CONFIG)
    assert evaluate([f("90022", "Medium")], config).outcomes == {"90022": "WARN"}
    quiet = evaluate([f("90022", "Medium")], config, default="INFO")
    assert quiet.outcomes == {"90022": "INFO"} and quiet.exit_code == 0
    assert evaluate([f("90022")], {}, default="FAIL").exit_code == 1
    with pytest.raises(ValueError):
        evaluate([], config, default="MAYBE")


def test_exit_status_uses_risk_or_greater():
    medium = [f("a"), f("b", "Medium")]
    assert exit_status(medium) == 0
    assert exit_status(medium, warn_level="Low") == 2
    assert exit_status(medium, warn_level="Medium") == 2
    assert exit_status(medium, warn_level="High") == 0
    assert exit_status(medium, error_level="Medium") == 1
    assert exit_status(medium, warn_level="Low", error_level="High") == 2
    assert exit_status([f("a", "High")], warn_level="Low", error_level="High") == 1


def test_exit_status_overrides_and_edge_cases():
    assert exit_status([f("a", "High")], error_level="High", error_exit_value=7) == 7
    assert exit_status([f("a")], warn_level="Low", warn_exit_value=5) == 5
    assert exit_status([], warn_level="Informational", ok_exit_value=3) == 3
    assert exit_status([f("a", "Informational")], warn_level="Informational") == 2
    with pytest.raises(ValueError):
        exit_status([], warn_level="Critical")
    with pytest.raises(ValueError):
        exit_status([], error_level="warn")
