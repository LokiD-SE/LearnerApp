"""Checks exercises/api/mass_exposure.py: hand-made bodies first, then the portal's merchant endpoint."""

import pytest
from api.mass_exposure import Exposure, check_merchant_exposure, find_sensitive, outside_contract
from apitop_fixture import tokens
from sandpay_vuln import make_app, serve

pytestmark = pytest.mark.exercise

DOCUMENTED = {"id", "name", "payout_iban_last4"}


def test_flags_key_names_that_hold_secrets():
    body = {"id": "m_1", "api_secret": "x", "owner": {"password_hash": "y"}, "items": [{"refresh_token": "z"}]}
    paths = {e.path for e in find_sensitive(body)}
    assert paths == {"$.api_secret", "$.owner.password_hash", "$.items[0].refresh_token"}
    assert all(e.reason == "sensitive key name" for e in find_sensitive(body))


def test_flags_a_full_iban_but_not_a_masked_one():
    assert find_sensitive({"payout": "GB82 WEST 1234 5698 7654 32"}) == [Exposure("$.payout", "full IBAN")]
    assert find_sensitive({"payout": "XX00 SAND 0000 0001"}) == [Exposure("$.payout", "full IBAN")]
    assert find_sensitive({"payout_iban_last4": "0001", "masked": "****0001"}) == []


def test_clean_bodies_have_no_findings():
    assert find_sensitive({"id": "m_1", "name": "Shop A", "tags": ["a", "b"], "n": 3, "ok": None}) == []
    assert find_sensitive([]) == [] and find_sensitive("hello") == []


def test_the_result_never_carries_the_value():
    for e in find_sensitive({"api_secret": "sk_test_value_123"}):
        assert "sk_test_value_123" not in repr(e)


def test_outside_contract_lists_extra_properties_sorted():
    body = {"id": "m", "name": "n", "payout_iban_last4": "1", "zeta": 1, "api_secret": "s"}
    assert outside_contract(body, DOCUMENTED) == [
        Exposure("$.api_secret", "not in the contract"),
        Exposure("$.zeta", "not in the contract"),
    ]
    assert outside_contract({"id": "m"}, DOCUMENTED) == []


def run(fixed):
    with serve(make_app(fixed)) as base:
        return check_merchant_exposure(base, tokens(base)["alice"], DOCUMENTED)


def test_finds_the_secret_and_the_full_iban_on_the_vulnerable_portal():
    found = run(set())
    paths = [e.path for e in found]
    assert paths == ["$.api_secret", "$.payout_iban"]  # contract breaches first, each path once
    assert found[0].reason == "not in the contract"


def test_reports_nothing_once_data_exposure_is_fixed():
    assert run({"data-exposure"}) == []


def test_refuses_a_verdict_when_the_token_does_not_work():
    with serve(make_app()) as base:
        with pytest.raises(RuntimeError):
            check_merchant_exposure(base, "bad", DOCUMENTED)
