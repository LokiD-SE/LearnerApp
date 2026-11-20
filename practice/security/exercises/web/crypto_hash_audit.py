"""EXERCISE - Read stored password hashes the way a tester does (WSTG-CRYP-04, Password Storage Cheat Sheet).

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


def classify_hash(stored: str) -> dict:
    """Returns ``{"algorithm": str, "salted": bool, "slow": bool, "findings": [codes, sorted]}``.

    ``slow`` is True only for a salted, adaptive scheme (PBKDF2, bcrypt, Argon2id) that meets the minimums above.
    An unrecognised value has algorithm ``"unknown"``, ``salted`` False, ``slow`` False and the single finding
    ``unrecognised-format``.
    """
    # TODO: match the formats in the module docstring (hex lengths, pbkdf2_sha256$..., $2b$..., $argon2id$...).
    # Parse the PBKDF2 iterations and the salt length (hex pairs = bytes) and apply the minimums.
    raise NotImplementedError("classify_hash")


def audit_hashes(stored_by_user: dict[str, str]) -> dict:
    """Returns ``{"users": {user: classify_hash(value)}, "shared": [[user, ...], ...]}``.

    ``shared`` lists every group of two or more users whose stored values are identical; users inside a group
    and the groups themselves are sorted.
    """
    # TODO: classify every user; group users by identical stored value and keep groups of two or more.
    raise NotImplementedError("audit_hashes")
