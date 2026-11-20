"""Session id analysis - WSTG-SESS-01 "session analysis": structure, information leakage and randomness.

A sample of ids cannot PROVE randomness (only a review of the generator can), but it can catch the failures
that matter: ids that are too short for 64 bits of entropy, positions that never change, ids that count up,
and duplicates. The OWASP Session Management Cheat Sheet's example is the model: a 16-hex-character id where
half the characters are fixed has only 32 bits of entropy.

Estimate used here (an upper bound, not a measurement): each position that varies in the sample contributes
log2(alphabet size) bits; positions that never vary contribute nothing.
"""

from __future__ import annotations

import math
import string
from dataclasses import dataclass, field

import requests

ALPHABETS = {
    "decimal": set(string.digits),
    "hex": set(string.hexdigits.lower()),
    "base64url": set(string.ascii_letters + string.digits + "-_"),
}
MIN_BITS = 64  # OWASP Session Management Cheat Sheet, "Session ID Entropy"


@dataclass
class IdReport:
    count: int
    alphabet: str  # decimal, hex, base64url or other
    lengths: tuple[int, int]  # (shortest, longest)
    fixed_positions: list[int]  # 0-based positions with the same character in every sample
    estimated_bits: float  # upper bound from the varying positions
    duplicates: int
    sequential: bool  # ids differ by small steps when read as numbers
    findings: list[str] = field(default_factory=list)


def classify_alphabet(ids: list[str]) -> str:
    """TODO: ``decimal`` if every character is a digit, else ``hex`` if all are hex digits (either case), else
    ``base64url`` (letters, digits, ``-`` and ``_``), else ``other``. Check in that order."""
    raise NotImplementedError("classify_alphabet")


def fixed_positions(ids: list[str]) -> list[int]:
    """TODO: Positions (0-based, up to the shortest id) where every id has the same character."""
    raise NotImplementedError("fixed_positions")


def numeric_value(sid: str) -> int | None:
    """The id read as a number: its longest run of hex characters (``s0003e9`` -> 0x3e9). None if none."""
    # TODO: The longest run of hex characters in the id, read as a base-16 number (``s0003e9`` -> 1001);
    # None if the id has no hex characters.
    raise NotImplementedError("numeric_value")


def is_sequential(ids: list[str], max_step: int = 1000) -> bool:
    """TODO: True when there are at least 3 ids, each has a numeric value, and every step between neighbours is
    a positive number no bigger than ``max_step``."""
    raise NotImplementedError("is_sequential")


def analyse_ids(ids: list[str]) -> IdReport:
    """TODO: Raise ValueError for fewer than 2 ids. Build the IdReport:
    - alphabet size: decimal 10, hex 16, base64url 64, other = number of distinct characters;
    - estimated_bits = (shortest length - number of fixed positions) x log2(size), rounded to 1 decimal;
    - findings: ``below-64-bits``, ``sequential``, ``duplicates``, and ``fixed-positions`` (when any
      position is fixed and the alphabet is not ``other``)."""
    raise NotImplementedError("analyse_ids")


def collect_ids(base_url: str, n: int, timeout: float = 5) -> list[str]:
    """``n`` fresh pre-login session ids, one per cookie-less GET /login."""
    # TODO: Make ``n`` cookie-less GET /login requests and return the ``sid`` each one sets
    # (RuntimeError if one sets none).
    raise NotImplementedError("collect_ids")


def is_weak(report: IdReport) -> bool:
    """Weak when the sample shows too little entropy, counting ids or repeats. ``fixed-positions`` alone is
    information: a fixed prefix is fine if the rest still carries 64 bits."""
    # TODO: True when the findings include ``below-64-bits``, ``sequential`` or ``duplicates``.
    raise NotImplementedError("is_weak")
