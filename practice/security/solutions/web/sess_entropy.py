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
    chars = set("".join(ids))
    lowered = {c.lower() for c in chars}
    for name in ("decimal", "hex", "base64url"):
        alphabet = ALPHABETS[name]
        if (lowered if name == "hex" else chars) <= alphabet:
            return name
    return "other"


def fixed_positions(ids: list[str]) -> list[int]:
    shortest = min(len(i) for i in ids)
    return [p for p in range(shortest) if len({i[p] for i in ids}) == 1]


def numeric_value(sid: str) -> int | None:
    """The id read as a number: its longest run of hex characters (``s0003e9`` -> 0x3e9). None if none."""
    best = ""
    run = ""
    for ch in sid.lower():
        if ch in string.hexdigits:
            run += ch
            best = max(best, run, key=len)
        else:
            run = ""
    return int(best, 16) if best else None


def is_sequential(ids: list[str], max_step: int = 1000) -> bool:
    values = [numeric_value(i) for i in ids]
    if len(ids) < 3 or any(v is None for v in values):
        return False
    steps = [b - a for a, b in zip(values, values[1:])]
    return all(0 < s <= max_step for s in steps)


def analyse_ids(ids: list[str]) -> IdReport:
    if len(ids) < 2:
        raise ValueError("collect at least two ids - one sample says nothing about what varies")
    alphabet = classify_alphabet(ids)
    size = {"decimal": 10, "hex": 16, "base64url": 64}.get(alphabet, len(set("".join(ids))))
    fixed = fixed_positions(ids)
    varying = min(len(i) for i in ids) - len(fixed)
    bits = varying * math.log2(size) if size > 1 else 0.0
    duplicates = len(ids) - len(set(ids))
    sequential = is_sequential(ids)
    findings = []
    if bits < MIN_BITS:
        findings.append("below-64-bits")
    if sequential:
        findings.append("sequential")
    if duplicates:
        findings.append("duplicates")
    if fixed and alphabet != "other":
        findings.append("fixed-positions")
    lengths = (min(len(i) for i in ids), max(len(i) for i in ids))
    return IdReport(len(ids), alphabet, lengths, fixed, round(bits, 1), duplicates, sequential, findings)


def collect_ids(base_url: str, n: int, timeout: float = 5) -> list[str]:
    """``n`` fresh pre-login session ids, one per cookie-less GET /login."""
    ids = []
    for _ in range(n):
        r = requests.get(f"{base_url}/login", timeout=timeout)
        sid = r.cookies.get("sid")
        if not sid:
            raise RuntimeError("GET /login set no sid cookie")
        ids.append(sid)
    return ids


def is_weak(report: IdReport) -> bool:
    """Weak when the sample shows too little entropy, counting ids or repeats. ``fixed-positions`` alone is
    information: a fixed prefix is fine if the rest still carries 64 bits."""
    return any(f in report.findings for f in ("below-64-bits", "sequential", "duplicates"))
