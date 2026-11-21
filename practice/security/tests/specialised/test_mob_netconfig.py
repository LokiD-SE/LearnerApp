"""Checks exercises/specialised/mob_netconfig.py: the configuration audit and the effective cleartext setting."""

import pytest
import mob_fixture as fx
from specialised.mob_netconfig import audit_config, effective_cleartext, parse_config

pytestmark = pytest.mark.exercise


def test_the_bad_config_gives_exactly_the_expected_findings():
    assert audit_config(fx.BAD_NSC) == [
        ("cleartext-base", "base-config"),
        ("cleartext-domain", "legacy.sandpay.example"),
        ("pin-expiry", "api.sandpay.example"),
        ("pin-no-backup", "api.sandpay.example"),
        ("user-ca-trusted", "base-config"),
    ]


def test_the_good_config_has_no_findings():
    assert audit_config(fx.GOOD_NSC) == []


def test_every_finding_code_has_a_weakness_in_the_fixture_table():
    for code, _where in audit_config(fx.BAD_NSC):
        assert fx.WEAKNESS_OF[code][2] in fx.CONTROLS


def test_a_user_ca_in_debug_overrides_is_not_reported():
    only_debug = (
        "<network-security-config><debug-overrides><trust-anchors>"
        '<certificates src="user"/></trust-anchors></debug-overrides></network-security-config>'
    )
    assert audit_config(only_debug) == []


def test_a_user_ca_in_a_domain_config_is_reported_for_that_domain():
    text = (
        "<network-security-config><domain-config><domain>Corp.Example</domain><domain>b.example</domain>"
        '<trust-anchors><certificates src="user"/></trust-anchors></domain-config></network-security-config>'
    )
    assert audit_config(text) == [("user-ca-trusted", "corp.example,b.example")]


def test_nested_domain_configs_are_audited_too():
    assert audit_config(fx.NESTED_NSC) == [
        ("cleartext-domain", "sandpay.example"),
    ]


def test_a_pin_set_with_two_pins_and_no_expiry_is_fine_and_one_pin_has_no_backup():
    one = (
        "<network-security-config><domain-config><domain>a.example</domain>"
        '<pin-set><pin digest="SHA-256">AAAA</pin></pin-set></domain-config></network-security-config>'
    )
    assert audit_config(one) == [("pin-no-backup", "a.example")]


def test_an_empty_config_has_no_findings():
    assert audit_config(fx.EMPTY_NSC) == []


def test_the_result_is_sorted_and_has_no_repeats():
    result = audit_config(fx.BAD_NSC)
    assert result == sorted(set(result))


def test_doctype_entities_bad_xml_and_a_wrong_root_are_refused():
    with pytest.raises(ValueError):
        parse_config('<!DOCTYPE x [<!ENTITY a "b">]><network-security-config/>')
    with pytest.raises(ValueError):
        parse_config("<network-security-config>")
    with pytest.raises(ValueError):
        parse_config("<manifest/>")
    with pytest.raises(ValueError):
        audit_config('<!ENTITY a "b"><network-security-config/>')


@pytest.mark.parametrize("sdk, expected", [(27, True), (28, False), (35, False), (23, True)])
def test_with_no_configuration_the_platform_default_depends_on_the_target(sdk, expected):
    assert effective_cleartext(fx.EMPTY_NSC, sdk, "api.sandpay.example") is expected


def test_the_base_config_value_beats_the_platform_default():
    assert effective_cleartext(fx.GOOD_NSC, 24, "anything.example") is False
    assert effective_cleartext(fx.BAD_NSC, 35, "anything.example") is True


def test_a_domain_config_beats_the_base_config():
    assert effective_cleartext(fx.BAD_NSC, 35, "legacy.sandpay.example") is True
    assert effective_cleartext(fx.GOOD_NSC, 35, "api.sandpay.example") is False


def test_a_domain_config_that_sets_nothing_inherits_the_base_config():
    # api.sandpay.example in BAD_NSC has a pin-set but no cleartext setting, so the base-config's "true" applies.
    assert effective_cleartext(fx.BAD_NSC, 35, "api.sandpay.example") is True


def test_subdomains_match_only_when_include_subdomains_is_true():
    assert effective_cleartext(fx.BAD_NSC, 35, "www.legacy.sandpay.example") is True
    assert effective_cleartext(fx.EXACT_NSC, 35, "status.sandpay.example") is True
    assert effective_cleartext(fx.EXACT_NSC, 35, "www.status.sandpay.example") is False


def test_a_look_alike_host_does_not_match():
    assert effective_cleartext(fx.NESTED_NSC, 35, "notsandpay.example") is False
    assert effective_cleartext(fx.NESTED_NSC, 27, "notsandpay.example") is True


def test_host_names_are_compared_ignoring_case_and_spaces():
    assert effective_cleartext(fx.NESTED_NSC, 35, " WWW.SandPay.Example ") is True


def test_the_nested_rule_with_the_longest_domain_wins_and_a_nested_rule_inherits_upwards():
    assert effective_cleartext(fx.NESTED_NSC, 35, "www.sandpay.example") is True
    assert effective_cleartext(fx.NESTED_NSC, 35, "secure.sandpay.example") is False
    assert effective_cleartext(fx.NESTED_NSC, 35, "x.secure.sandpay.example") is False


def test_a_nested_config_that_sets_nothing_takes_its_parents_value():
    text = (
        '<network-security-config><domain-config cleartextTrafficPermitted="true"><domain includeSubdomains="true">a.example</domain>'
        '<domain-config><domain includeSubdomains="true">b.a.example</domain></domain-config></domain-config></network-security-config>'
    )
    assert effective_cleartext(text, 35, "x.b.a.example") is True
