"""EXERCISE - Plan the testing of ONE feature from what it does, and find what a candidate's plan misses (mock interview).

The scenario question: "How would you test this feature?" A good answer does not list every test in the guide;
it asks what the feature does and picks the categories that its behaviour calls for, then says what it would
leave out and why. This module is that reasoning as code.

The categories are the twelve headings of the OWASP Web Security Testing Guide v4.2 checklist (see
``smi_fixture.CATEGORIES``). Which feature flag calls for which category is in ``smi_fixture.RULES``; that table
is this lesson's judgement, not OWASP's.
"""

from __future__ import annotations

import re
from typing import Iterable

from smi_fixture import BASELINE, CATEGORIES, FLAGS, PREFIX_ALIASES, RULES, Feature, Gaps

TEST_ID = re.compile(r"^WSTG-([A-Z]+)-(\d{2})$")


def _test_prefix(heading_suffix: str) -> str:
    return next(k for k, v in PREFIX_ALIASES.items() if v == heading_suffix)


def category_of(ref: str) -> str:
    """The checklist category heading of a category or test id.

    ``"WSTG-ATHZ"`` is already a heading and is returned as it is. A test id such as ``"WSTG-ATHZ-04"`` (prefix,
    dash, two digits) maps to its heading; the two prefixes that differ from their heading go through
    ``PREFIX_ALIASES`` (``WSTG-BUSL-05`` -> ``WSTG-BUSLOGIC``, ``WSTG-CLNT-04`` -> ``WSTG-CLIENT``).
    Raise ``ValueError`` for anything else: a malformed id (``WSTG-ATHZ-4``), a prefix that is not a category, or a
    heading used as a test prefix (``WSTG-BUSLOGIC-01`` - the tests of that category are ``WSTG-BUSL-..``).
    """
    raise NotImplementedError("TODO: implement category_of")


def required_areas(feature: Feature) -> dict[str, list[str]]:
    """The categories this feature needs, each with the reasons: ``{category: sorted reasons}``.

    Every feature gets the ``BASELINE`` categories with the reason ``"baseline"``. For every flag of the feature that
    is True, the categories ``RULES[flag]`` are added with the flag's name as the reason. A category called for
    twice lists both reasons. The result is in ``CATEGORIES`` order and holds only the categories that are needed.
    """
    raise NotImplementedError("TODO: implement required_areas")


def plan_gaps(feature: Feature, planned: Iterable[str]) -> Gaps:
    """Compare a plan with what the feature needs.

    Each planned entry is a category or a test id; map it with ``category_of`` (so an unknown entry raises
    ``ValueError``). ``missing`` - needed and absent. ``unneeded`` - planned, but no flag calls for it.
    Both are tuples in ``CATEGORIES`` order, with no repeats.
    """
    raise NotImplementedError("TODO: implement plan_gaps")
