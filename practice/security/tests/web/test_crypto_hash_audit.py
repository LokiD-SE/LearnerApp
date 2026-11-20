"""Checks practice/security/exercises/web/crypto_hash_audit.py (testing-cryptography-and-data-exposure lesson)."""

import pytest
from sandpay_vuln import make_app
from web.crypto_hash_audit import audit_hashes, classify_hash

pytestmark = pytest.mark.exercise

MD5 = "5f4dcc3b5aa765d61d8327deb882cf99"
PBKDF2 = "pbkdf2_sha256$600000$" + "ab" * 16 + "$" + "cd" * 32


def stored_hashes(app):
    return {row["email"]: row["password_hash"] for row in app.query("SELECT email, password_hash FROM users")}


def test_fast_unsalted_hashes_are_recognised_by_length():
    assert classify_hash(MD5) == {"algorithm": "md5", "salted": False, "slow": False, "findings": ["fast-hash", "unsalted"]}
    assert classify_hash("a" * 40)["algorithm"] == "sha1"
    assert classify_hash("b" * 64)["algorithm"] == "sha256"
    assert classify_hash("b" * 64)["findings"] == ["fast-hash", "unsalted"]


def test_a_conforming_pbkdf2_value_has_no_findings():
    assert classify_hash(PBKDF2) == {"algorithm": "pbkdf2-sha256", "salted": True, "slow": True, "findings": []}


def test_pbkdf2_minimums():
    low = classify_hash("pbkdf2_sha256$10000$" + "ab" * 16 + "$" + "cd" * 32)
    assert low["findings"] == ["low-iterations"] and low["salted"] and not low["slow"]
    short = classify_hash("pbkdf2_sha256$600000$abab$" + "cd" * 32)  # 2-byte salt
    assert short["findings"] == ["short-salt"] and not short["slow"]
    both = classify_hash("pbkdf2_sha256$1000$ab$" + "cd" * 32)
    assert both["findings"] == ["low-iterations", "short-salt"]


def test_bcrypt_argon2_and_garbage():
    assert classify_hash("$2b$12$" + "x" * 53) == {"algorithm": "bcrypt", "salted": True, "slow": True, "findings": []}
    assert classify_hash("$2y$04$" + "x" * 53)["findings"] == ["low-cost"]
    assert classify_hash("$argon2id$v=19$m=19456,t=2,p=1$c2FsdA$aGFzaA") == {
        "algorithm": "argon2id", "salted": True, "slow": True, "findings": []}
    for odd in ("", "hunter2", "pbkdf2_sha256$x$y", "ZZ" * 16):
        assert classify_hash(odd) == {"algorithm": "unknown", "salted": False, "slow": False,
                                      "findings": ["unrecognised-format"]}


def test_identical_values_for_different_users_are_reported_as_shared():
    audit = audit_hashes({"carol": MD5, "alice": MD5, "bob": "0" * 32, "dave": PBKDF2, "erin": PBKDF2, "frank": "1" * 32})
    assert audit["shared"] == [["alice", "carol"], ["dave", "erin"]]
    assert list(audit["users"]) == ["alice", "bob", "carol", "dave", "erin", "frank"]
    assert audit["users"]["dave"]["findings"] == []


def test_the_vulnerable_portal_stores_unsalted_md5():
    audit = audit_hashes(stored_hashes(make_app()))
    assert {u["algorithm"] for u in audit["users"].values()} == {"md5"}
    assert all(u["findings"] == ["fast-hash", "unsalted"] for u in audit["users"].values())
    assert audit["shared"] == []  # three different passwords: unsalted, but nobody shares one yet


def test_the_fixed_portal_stores_salted_pbkdf2_and_reports_nothing():
    audit = audit_hashes(stored_hashes(make_app({"weak-hash"})))
    assert {u["algorithm"] for u in audit["users"].values()} == {"pbkdf2-sha256"}
    assert all(u["findings"] == [] and u["slow"] for u in audit["users"].values())


def test_same_password_gives_the_same_md5_but_not_the_same_pbkdf2():
    from sandpay_vuln import _md5, _pbkdf2  # the portal's own two storage functions

    same_md5 = {"alice": _md5("Summer2026-x"), "bob": _md5("Summer2026-x"), "carol": _md5("another-one")}
    assert audit_hashes(same_md5)["shared"] == [["alice", "bob"]]
    same_pbkdf2 = {"alice": _pbkdf2("Summer2026-x"), "bob": _pbkdf2("Summer2026-x")}
    audit = audit_hashes(same_pbkdf2)
    assert audit["shared"] == []  # a random salt per password: equal passwords no longer look equal
    assert all(u["findings"] == [] for u in audit["users"].values())
