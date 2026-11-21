"""Checks exercises/api/mass_fix.py: the allow-list for input and the response model for output."""

import pytest
from api.mass_fix import apply_profile_update, merchant_view

pytestmark = pytest.mark.exercise

USER = {"id": 1, "email": "alice@shop-a.example", "merchant_id": "m_100", "role": "merchant",
        "display_name": "Alice"}


def test_applies_an_allowed_field_to_a_copy():
    updated = apply_profile_update(USER, {"display_name": "  Alice B  "})
    assert updated["display_name"] == "Alice B"
    assert USER["display_name"] == "Alice"  # the original is untouched
    assert updated is not USER
    assert {k: v for k, v in updated.items() if k != "display_name"} == {
        k: v for k, v in USER.items() if k != "display_name"}


def test_an_empty_payload_changes_nothing():
    assert apply_profile_update(USER, {}) == USER


@pytest.mark.parametrize("payload, names", [
    ({"role": "admin"}, ["role"]),
    ({"display_name": "A", "merchant_id": "m_200", "role": "admin"}, ["merchant_id", "role"]),
    ({"is_admin": True}, ["is_admin"]),
    ({"id": 7}, ["id"]),
])
def test_rejects_every_field_outside_the_allow_list(payload, names):
    with pytest.raises(ValueError) as err:
        apply_profile_update(USER, payload)
    assert str(err.value) == f"fields not allowed: {names}"


def test_a_rejected_request_applies_nothing():
    snapshot = dict(USER)
    with pytest.raises(ValueError):
        apply_profile_update(USER, {"display_name": "Mallory", "role": "admin"})
    assert USER == snapshot


@pytest.mark.parametrize("bad", ["", "   ", "x" * 61, 42, None, ["a"]])
def test_validates_the_allowed_field_too(bad):
    with pytest.raises(ValueError):
        apply_profile_update(USER, {"display_name": bad})


def test_sixty_characters_is_the_limit():
    assert apply_profile_update(USER, {"display_name": "x" * 60})["display_name"] == "x" * 60


ROW = {"id": "m_100", "name": "Shop A", "api_secret": "sk_test_shop_a_practice",
       "payout_iban": "XX00 SAND 0000 0001"}


def test_merchant_view_has_exactly_three_properties():
    assert merchant_view(ROW) == {"id": "m_100", "name": "Shop A", "payout_iban_last4": "0001"}


def test_merchant_view_never_leaks_the_secret_or_the_full_iban():
    text = repr(merchant_view(ROW))
    assert "sk_test" not in text and "SAND" not in text


def test_merchant_view_does_not_depend_on_extra_columns():
    assert merchant_view({**ROW, "password_hash": "h", "internal_note": "n"}) == merchant_view(ROW)
