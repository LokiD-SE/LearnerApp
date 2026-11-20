"""SOLUTION - Read stored password hashes the way a tester does (WSTG-CRYP-04, Password Storage Cheat Sheet).

With the owner's permission and a read of the user table you do NOT crack anything. You look at the FORMAT of
each stored value and answer three questions: which algorithm, is there a per-password salt, is it slow?

- ``classify_hash`` - one stored value -> algorithm, salted, slow and a list of finding codes.
- ``audit_hashes`` - a whole user table -> a classification per user, plus the groups of users whose stored
  values are identical (two different users with the same stored value is evidence of a missing salt).

Recognised formats (the SandPay portal writes the first and the fourth):

| format                                          | algorithm       |
| ----------------------------------------------- | --------------- |
| 32 hex characters                               | ``md5``         |
| 40 hex characters                               | ``sha1``        |
| 64 hex characters                               | ``sha256``      |
| ``pbkdf2_sha256$<iterations>$<salt hex>$<hex>`` | ``pbkdf2-sha256`` |
| ``$2a$ / $2b$ / $2y$<cost>$...``                | ``bcrypt``      |
| ``$argon2id$...``                               | ``argon2id``    |

Finding codes: ``fast-hash`` (MD5, SHA-1 or plain SHA-256: designed to be fast), ``unsalted`` (no salt in the
format), ``low-iterations`` (PBKDF2 below 600000, the Password Storage Cheat Sheet's figure for PBKDF2-HMAC-SHA256),
``low-cost`` (bcrypt below 10), ``short-salt`` (PBKDF2 salt under 4 bytes = 32 bits, NIST SP 800-63B-4),
``unrecognised-format``.
"""

from __future__ import annotations

import re

MIN_PBKDF2_ITERATIONS = 600_000
MIN_BCRYPT_COST = 10
MIN_SALT_BYTES = 4  # 32 bits


_HEX = re.compile(r"^[0-9a-f]+$")
_BCRYPT = re.compile(r"^\$2[aby]\$(\d{2})\$")
_FAST = {32: "md5", 40: "sha1", 64: "sha256"}


def classify_hash(stored: str) -> dict:
    """Returns ``{"algorithm": str, "salted": bool, "slow": bool, "findings": [codes, sorted]}``."""
    findings: set[str] = set()
    if _HEX.match(stored) and len(stored) in _FAST:
        return {"algorithm": _FAST[len(stored)], "salted": False, "slow": False,
                "findings": sorted({"fast-hash", "unsalted"})}
    if stored.startswith("pbkdf2_sha256$"):
        parts = stored.split("$")
        if len(parts) == 4 and parts[1].isdigit() and _HEX.match(parts[2]) and _HEX.match(parts[3]):
            if int(parts[1]) < MIN_PBKDF2_ITERATIONS:
                findings.add("low-iterations")
            if len(parts[2]) // 2 < MIN_SALT_BYTES:
                findings.add("short-salt")
            return {"algorithm": "pbkdf2-sha256", "salted": True, "slow": not findings, "findings": sorted(findings)}
    bcrypt = _BCRYPT.match(stored)
    if bcrypt:
        low = int(bcrypt.group(1)) < MIN_BCRYPT_COST
        return {"algorithm": "bcrypt", "salted": True, "slow": not low, "findings": ["low-cost"] if low else []}
    if stored.startswith("$argon2id$"):
        return {"algorithm": "argon2id", "salted": True, "slow": True, "findings": []}
    return {"algorithm": "unknown", "salted": False, "slow": False, "findings": ["unrecognised-format"]}


def audit_hashes(stored_by_user: dict[str, str]) -> dict:
    """Returns ``{"users": {user: classify_hash(value)}, "shared": [[user, ...], ...]}``."""
    by_value: dict[str, list[str]] = {}
    for user, stored in stored_by_user.items():
        by_value.setdefault(stored, []).append(user)
    return {
        "users": {user: classify_hash(stored) for user, stored in sorted(stored_by_user.items())},
        "shared": sorted(sorted(users) for users in by_value.values() if len(users) > 1),
    }
