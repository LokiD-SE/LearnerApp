"""JMeter's Regular Expression Extractor, emulated in Python - EXERCISE.

Implement the two functions so that a page of SandPay JSON gives the same variables JMeter 5.6.3 sets. The
rules (JMeter Component Reference, "Regular Expression Extractor"):

- The template turns one match into a string: ``$1$`` is group 1, ``$2$`` group 2, ``$0$`` the whole match;
  any other text is copied as it is.
- Match number N > 0: use the N-th match. 0: a random match (use ``rng``). Negative: every match.
- Non-negative and a match found: ``ref`` = the template value, ``ref_gN`` = group N (0 = whole match) and
  ``ref_g`` = the number of groups (excluding 0).
- Non-negative and no match: ``ref`` = the default (left unchanged when ``default`` is None), and ``ref_g0``,
  ``ref_g1`` ... and ``ref_g`` are removed.
- Negative: ``ref_matchNr`` = the number of matches (could be 0), ``ref_n`` = the template for match n,
  ``ref_n_gm`` = group m of match n, ``ref_n_g`` = the number of groups, and ``ref`` is always set to the
  default (when there is one).

Run: .venv/bin/python -m pytest tests/jmeter/test_jm_corr_regex.py
"""

from __future__ import annotations

import random
import re


def render_template(template: str, match: re.Match) -> str:
    """Replaces every ``$N$`` in the template with group N of the match; other text is kept."""
    raise NotImplementedError("TODO: replace $N$ with match.group(N)")


def extract(
    variables: dict[str, str],
    text: str,
    ref: str,
    regex: str,
    template: str = "$1$",
    match_no: int = 1,
    default: str | None = None,
    rng: random.Random | None = None,
) -> dict[str, str]:
    """Returns a NEW variables dict after applying one extractor to ``text`` (the input is not changed)."""
    raise NotImplementedError("TODO: apply the match-number rules above")
