"""Checks exercises/specialised/spay_audit.py: leak and token audits of the practice card gateway."""

import re

import pytest
import spay_fixture as fx
from specialised.spay_audit import audit_card_data, audit_tokens, exposed_digits

pytestmark = pytest.mark.exercise

CARD_FLAWS = ["pan-in-response", "pan-in-log", "pan-stored-plain", "cvv-stored", "unmasked-display"]
TOKEN_FLAWS = ["token-guessable", "token-cross-merchant"]


def gateway_with_only(*flaws):
    """A gateway where every flaw is fixed except the named ones."""
    return fx.CardGateway(fixed=set(fx.FLAWS) - set(flaws))


@pytest.mark.parametrize("flaw", CARD_FLAWS)
def test_each_card_data_flaw_is_found_alone(flaw):
    assert audit_card_data(gateway_with_only(flaw)) == [flaw]


@pytest.mark.parametrize("flaw", TOKEN_FLAWS)
def test_each_token_flaw_is_found_alone(flaw):
    assert audit_tokens(gateway_with_only(flaw)) == [flaw]


def test_the_default_gateway_has_every_card_data_flaw_sorted():
    assert audit_card_data(fx.CardGateway()) == sorted(CARD_FLAWS)


def test_the_default_gateway_has_both_token_flaws_sorted():
    assert audit_tokens(fx.CardGateway()) == sorted(TOKEN_FLAWS)


def test_a_fully_fixed_gateway_gives_no_false_positive():
    fixed = fx.CardGateway(fixed=fx.FLAWS)
    assert audit_card_data(fixed) == []
    assert audit_tokens(fixed) == []


def test_the_velocity_flaw_is_not_a_card_data_or_token_flaw():
    gateway = gateway_with_only("no-velocity")
    assert audit_card_data(gateway) == []
    assert audit_tokens(gateway) == []


def test_findings_never_contain_a_card_number():
    gateway = fx.CardGateway()
    found = audit_card_data(gateway) + audit_tokens(gateway)
    assert not re.search(r"[0-9]{6,}", repr(found))


def test_the_audit_pays_once_as_the_audit_client():
    gateway = fx.CardGateway()
    audit_card_data(gateway, merchant="m_900")
    records = gateway.export_records()
    assert len(records) == 1
    assert records[0]["merchant"] == "m_900" and records[0]["amount_minor"] == 1000
    assert any("client=audit-client" in line for line in gateway.log)


def test_a_declined_audit_card_is_an_error_not_a_clean_report():
    gateway = fx.CardGateway()
    gateway.authorize = lambda *args, **kwargs: (402, {"error": "card_declined"})
    with pytest.raises(RuntimeError):
        audit_card_data(gateway)


def test_a_refused_tokenisation_is_an_error():
    gateway = fx.CardGateway()
    gateway.tokenize = lambda *args, **kwargs: (503, {"error": "down"})
    with pytest.raises(RuntimeError):
        audit_tokens(gateway)


def test_the_pan_is_found_even_when_it_is_written_in_groups():
    gateway = gateway_with_only()
    card = gateway.test_cards[0]
    grouped = " ".join(card["pan"][i:i + 4] for i in range(0, 16, 4))
    original = gateway.authorize

    def noisy(*args, **kwargs):
        status, body = original(*args, **kwargs)
        body["note"] = f"paid with {grouped}"
        return status, body

    gateway.authorize = noisy
    assert audit_card_data(gateway) == ["pan-in-response"]


@pytest.mark.parametrize("shown_first, shown_last, expected", [(6, 4, 10), (8, 4, 12), (16, 0, 16), (0, 0, 0), (0, 4, 4)])
def test_exposed_digits_counts_the_digits_one_display_shows(shown_first, shown_last, expected):
    pan = fx.make_test_pan("4", 16, 5)
    hidden = 16 - shown_first - shown_last
    shown = pan[:shown_first] + "*" * hidden + pan[16 - shown_last:]
    assert exposed_digits(f"card {shown} ok", pan) == expected


def test_exposed_digits_ignores_other_numbers_and_wrong_digits():
    pan = fx.make_test_pan("4", 16, 5)
    other = fx.make_test_pan("4", 16, 6)
    assert exposed_digits(f"amount 2500 on {other}", pan) < 6
    assert exposed_digits("no card here", pan) == 0
