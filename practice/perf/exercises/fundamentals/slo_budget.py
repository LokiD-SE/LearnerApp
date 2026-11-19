"""Exercise slo_budget: error budgets and burn rate, with exact decimal arithmetic.

From the Google SRE workbook ("Implementing SLOs"): "the error budget is 100% minus the SLO. For example, if you
have a 99.9% success ratio SLO, then a service that receives 3 million requests over a four-week period had a
budget of 3,000 (0.1%) errors over that period. If a single outage is responsible for 1,500 errors, that error
costs 50% of the error budget." And ("Alerting on SLOs"): "Burn rate is how fast, relative to the SLO, the
service consumes the error budget" - a burn rate of 1 leaves exactly 0 budget at the end of the window.

SLOs are passed as strings ("99.9") so no binary floating-point rounding creeps into money-like counts.
"""

from __future__ import annotations

from decimal import Decimal


def _slo(slo_percent: str | Decimal) -> Decimal:
    slo = Decimal(str(slo_percent))
    if not Decimal(0) < slo < Decimal(100):
        raise ValueError("an SLO must be between 0 and 100 percent, exclusive - 100% leaves no budget at all")
    return slo


def error_budget(slo_percent: str | Decimal, total_events: int) -> Decimal:
    """How many bad events the SLO allows out of ``total_events``."""
    # TODO: (100 - SLO) / 100 * total; ValueError for a negative total.
    raise NotImplementedError("error_budget")


def budget_consumed(slo_percent: str | Decimal, total_events: int, bad_events: int) -> Decimal:
    """Fraction of the budget used: 0.5 is half, 1 is all of it, above 1 means the SLO is missed."""
    # TODO: bad / budget; ValueError when the budget is 0.
    raise NotImplementedError("budget_consumed")


def burn_rate(slo_percent: str | Decimal, observed_error_percent: str | Decimal) -> Decimal:
    """Observed error rate divided by the error rate the SLO allows."""
    # TODO: observed error % / (100 - SLO).
    raise NotImplementedError("burn_rate")


def days_to_exhaustion(window_days: int, rate: Decimal) -> Decimal | None:
    """At a constant burn rate, how long a full budget lasts; None when nothing is burning."""
    # TODO: window / rate; None when rate <= 0.
    raise NotImplementedError("days_to_exhaustion")


def release_allowed(slo_percent: str | Decimal, total_events: int, bad_events: int) -> bool:
    """The SRE book's rule: releases go out "as long as there is error budget remaining"."""
    # TODO: True while less than the whole budget is consumed.
    raise NotImplementedError("release_allowed")