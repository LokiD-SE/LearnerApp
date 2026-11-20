"""Checks practice/security/exercises/web/auth_policy.py (testing-authentication lesson)."""

import pytest
from web.auth_policy import audit_policy, check_password

pytestmark = pytest.mark.exercise

BLOCK = {"password123456789", "sandpaysandpay123", "qwertyuiopasdfgh"}


def test_length_depends_on_how_the_password_is_used():
    assert check_password("fourteen-chars") == ["too-short"]  # 14
    assert check_password("fifteen--chars!") == []  # 15
    assert check_password("eight-ch", single_factor=False) == []
    assert check_password("seven-c", single_factor=False) == ["too-short"]


def test_no_composition_rules():
    assert check_password("correct horse battery staple") == []  # no digit, no capital, no symbol


def test_length_counts_code_points_after_nfc():
    composed = "café-au-lait-noir"  # 16 code points
    decomposed = "café-au-lait-noir"  # 17 code points before NFC, 16 after
    assert check_password(composed) == [] and check_password(decomposed) == []
    assert check_password("é" * 14) == ["too-short"]  # 14 characters, 28 bytes in UTF-8


def test_whole_password_compared_case_insensitively():
    assert check_password("Password123456789", blocklist=BLOCK) == ["blocklisted"]
    assert check_password("my-password123456789-is-long", blocklist=BLOCK) == []  # substrings are not compared


def test_context_words():
    assert check_password("alice@shop-a.example", context_words=["alice@shop-a.example", "SandPay"]) == ["context-word"]
    assert check_password("sandpay", context_words=["SandPay"]) == ["too-short", "context-word"]


def test_max_length():
    assert check_password("x" * 64) == []
    assert check_password("x" * 65) == ["too-long"]
    assert check_password("x" * 100, max_length=128) == []
    with pytest.raises(ValueError):
        check_password("anything-long-enough", max_length=32)


def test_audit_finds_every_conflict():
    legacy = {"min_length": 8, "max_length": 16, "composition_rules": True, "expiry_days": 90, "blocklist": False,
              "hints": True, "security_questions": True, "truncates": True}
    assert audit_policy(legacy) == [
        ("composition-rules", "SHALL"), ("hints-allowed", "SHALL"), ("max-length-below-64", "SHOULD"),
        ("min-length-below-15", "SHALL"), ("no-blocklist", "SHALL"), ("periodic-expiry", "SHALL"),
        ("security-questions", "SHALL"), ("truncation", "SHALL"),
    ]


def test_audit_accepts_a_conforming_policy():
    assert audit_policy({"min_length": 15, "max_length": None, "blocklist": True}) == []
    assert audit_policy({"single_factor": False, "min_length": 8, "max_length": 64, "blocklist": True}) == []


def test_audit_multi_factor_minimum():
    assert audit_policy({"single_factor": False, "min_length": 6, "blocklist": True}) == [("min-length-below-8", "SHALL")]
