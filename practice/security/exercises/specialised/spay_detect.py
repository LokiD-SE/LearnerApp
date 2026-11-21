"""EXERCISE - find card numbers in text, and mask them.

A log line, a response body or a support ticket may hold a full card number (a PAN). This module finds them without
keeping them.

* ``luhn_valid(digits)`` - the Luhn check. ``digits`` is a string of digits only. Starting from the RIGHT-most digit
  (which is digit 0), double every second digit (digits 1, 3, 5, ...); if a doubled digit is above 9, subtract 9; add all
  the digits; the number passes when the total is a multiple of 10. Return False for fewer than two characters or for a
  string that is not all digits.
* ``mask_pan(digits)`` - keep the first 6 digits, replace the middle with ``*`` and keep the last 4, but ALWAYS hide at
  least 4 digits: for a 13-digit number that means the first 6 and the last 3. Raise ``ValueError`` unless ``digits`` is
  13 to 19 digits. (PCI SSC FAQ 1091: "A maximum of the first 6 and last 4 digits of the PAN is the starting baseline".)
* ``find_pans(text)`` - every PAN in ``text``, in order, as ``PanHit(start, end, length, masked)``. A PAN is a run of 13
  to 19 digits, each optionally followed by ONE space or hyphen (``CANDIDATE`` is given), that is not part of a longer
  run of digits and that passes the Luhn check. ``start``/``end`` are the positions of the whole match in ``text``
  (separators included); ``length`` counts digits; ``masked`` is ``mask_pan`` of the digits. A hit never holds the full
  number.
* ``redact(text)`` - ``text`` with every hit replaced by its masked form. Everything else is untouched.

House rules, not standards. Luhn only catches typing mistakes: about one random 16-digit run in ten passes it, so a
scanner finds candidates, not proof.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CANDIDATE = re.compile(r"(?<![0-9])(?:[0-9][ -]?){12,18}[0-9](?![0-9])")
SEPARATORS = re.compile(r"[ -]")


@dataclass(frozen=True)
class PanHit:
    start: int
    end: int
    length: int
    masked: str  # never the full number


def luhn_valid(digits: str) -> bool:
    raise NotImplementedError("TODO: implement luhn_valid")


def mask_pan(digits: str) -> str:
    raise NotImplementedError("TODO: implement mask_pan")


def find_pans(text: str) -> list[PanHit]:
    raise NotImplementedError("TODO: implement find_pans")


def redact(text: str) -> str:
    raise NotImplementedError("TODO: implement redact")
