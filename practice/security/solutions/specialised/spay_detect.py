"""SOLUTION - find card numbers in text, and mask them."""

from __future__ import annotations

import re
from dataclasses import dataclass

# 13 to 19 digits, each optionally followed by one space or hyphen, not part of a longer run of digits.
CANDIDATE = re.compile(r"(?<![0-9])(?:[0-9][ -]?){12,18}[0-9](?![0-9])")
SEPARATORS = re.compile(r"[ -]")


@dataclass(frozen=True)
class PanHit:
    start: int
    end: int
    length: int
    masked: str  # never the full number


def luhn_valid(digits: str) -> bool:
    if len(digits) < 2 or not digits.isdigit():
        return False
    total = 0
    for index, ch in enumerate(reversed(digits)):
        d = int(ch)
        if index % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def mask_pan(digits: str) -> str:
    if not 13 <= len(digits) <= 19 or not digits.isdigit():
        raise ValueError("a PAN has 13 to 19 digits")
    masked = max(4, len(digits) - 10)
    return digits[:6] + "*" * masked + digits[6 + masked:]


def find_pans(text: str) -> list[PanHit]:
    hits = []
    for match in CANDIDATE.finditer(text):
        digits = SEPARATORS.sub("", match.group())
        if luhn_valid(digits):
            hits.append(PanHit(match.start(), match.end(), len(digits), mask_pan(digits)))
    return hits


def redact(text: str) -> str:
    out, last = [], 0
    for hit in find_pans(text):
        out.append(text[last:hit.start])
        out.append(hit.masked)
        last = hit.end
    out.append(text[last:])
    return "".join(out)
