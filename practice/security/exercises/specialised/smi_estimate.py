"""EXERCISE - Size a security assessment with numbers you can defend (mock interview).

The scoping question: "How long would you need to test this application?" The honest answer is a model with
stated assumptions, not a single number from memory: hours per endpoint, an uplift for every extra role (access
control is tested again for each), fixed hours for uploads and integrations, setup, and the three overheads
people forget - the report, the re-test of the fixes and contingency.

The rates in ``smi_fixture.PRACTICE_RATES`` are ASSUMPTIONS for practice, not benchmarks; in an interview you say
so, and say where the real figures would come from (your own past engagements, timed).
"""

from __future__ import annotations

import math

from smi_fixture import Estimate, Inventory, Rates


# Provided - the same checks every function of this module needs.
def _check(inventory: Inventory, rates: Rates) -> None:
    if inventory.endpoints < 0 or inventory.uploads < 0 or inventory.integrations < 0:
        raise ValueError("endpoints, uploads and integrations must be 0 or more")
    if inventory.roles < 1:
        raise ValueError("an application has at least one role")
    numbers = (
        rates.hours_per_endpoint, rates.role_uplift, rates.hours_per_upload, rates.hours_per_integration,
        rates.setup_hours, rates.report_fraction, rates.retest_fraction, rates.contingency_fraction,
    )
    if any(n < 0 for n in numbers) or rates.hours_per_day <= 0:
        raise ValueError("rates must be 0 or more, and hours_per_day above 0")


def effort_hours(inventory: Inventory, rates: Rates) -> float:
    """Hours of testing, setup included::

        endpoints x hours_per_endpoint x (1 + role_uplift x (roles - 1))
        + uploads x hours_per_upload + integrations x hours_per_integration + setup_hours

    Raise ``ValueError`` for a negative count or rate, ``roles`` below 1, or ``hours_per_day`` of 0 or less.
    """
    raise NotImplementedError("TODO: implement effort_hours")


def estimate(inventory: Inventory, rates: Rates) -> Estimate:
    """The hours of the whole assessment.

    ``effort_hours`` as above; ``report_hours`` = report_fraction x test hours; ``retest_hours`` = retest_fraction x
    test hours; ``contingency_hours`` = contingency_fraction x (test + report + retest); ``total_hours`` = all four.
    """
    raise NotImplementedError("TODO: implement estimate")


def person_days(total_hours: float, hours_per_day: float) -> float:
    """Person-days, rounded UP to the next half day (``0.5`` steps): you cannot book 3.2 days of someone's week.

    Round the quotient to 9 decimals before rounding up, so a float error just above 12 does not become 12.5.
    Raise ``ValueError`` for negative hours or ``hours_per_day`` of 0 or less.
    """
    raise NotImplementedError("TODO: implement person_days")


def calendar_days(person_day_count: float, testers: int, utilisation: float = 0.8) -> int:
    """Working days on the calendar: ``person_day_count / (testers x utilisation)``, rounded up to a whole day.

    ``utilisation`` is the share of a day a tester really spends on the engagement (meetings, waiting for access),
    above 0 and at most 1. Raise ``ValueError`` for ``testers`` below 1 or an ``utilisation`` outside (0, 1].
    More testers do not shorten setup and reporting in real life; this model ignores that, and says so.
    """
    raise NotImplementedError("TODO: implement calendar_days")
