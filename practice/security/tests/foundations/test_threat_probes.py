"""Exercise: foundations/threat_probes.py - threats from the register as executable checks.

Each check must find its threat in the vulnerable portal AND stay quiet once the one flaw it relies on is
fixed - a check that is always True proves nothing. ``lockout_denial`` is the other way round: it tests a
threat the fix creates."""

import base64
import json

import pytest
from foundations.threat_probes import (
    disclosure_cross_merchant,
    elevation_via_profile_update,
    lockout_denial,
    spoofing_by_guessing,
    spoofing_unsigned_token,
    unsigned_token,
)
from sandpay_vuln import make_app, serve

pytestmark = pytest.mark.exercise

ALICE = ("alice@shop-a.example", "alice-pass-1")
CHECKS = {
    "jwt-none": lambda base: spoofing_unsigned_token(base),
    "mass-assignment": lambda base: elevation_via_profile_update(base, *ALICE),
    "idor": lambda base: disclosure_cross_merchant(base, *ALICE, "pay_2001"),
    "no-rate-limit": lambda base: spoofing_by_guessing(base, ALICE[0]),
}


def run(check, fixed=()):
    with serve(make_app(fixed)) as base:
        return check(base)


def test_unsigned_token_shape():
    token = unsigned_token({"sub": "ops@sandpay.example"})
    header, payload, signature = token.split(".")
    pad = lambda s: s + "=" * (-len(s) % 4)  # noqa: E731
    assert json.loads(base64.urlsafe_b64decode(pad(header)))["alg"] == "none"
    assert json.loads(base64.urlsafe_b64decode(pad(payload))) == {"sub": "ops@sandpay.example"}
    assert signature == ""
    assert "=" not in token


@pytest.mark.parametrize("flaw", sorted(CHECKS))
def test_check_finds_the_threat(flaw):
    assert run(CHECKS[flaw]) is True


@pytest.mark.parametrize("flaw", sorted(CHECKS))
def test_check_is_quiet_when_its_flaw_is_fixed(flaw):
    assert run(CHECKS[flaw], fixed={flaw}) is False


def test_disclosure_check_is_quiet_for_own_payment():
    assert run(lambda base: disclosure_cross_merchant(base, *ALICE, "pay_1001")) is False


def test_lockout_is_a_threat_the_fix_creates():
    assert run(lambda base: lockout_denial(base, *ALICE)) is False
    assert run(lambda base: lockout_denial(base, *ALICE), fixed={"no-rate-limit"}) is True
