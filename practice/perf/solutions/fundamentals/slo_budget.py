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
    if total_events < 0:
        raise ValueError("total_events must not be negative")
    return (Decimal(100) - _slo(slo_percent)) / Decimal(100) * total_events


def budget_consumed(slo_percent: str | Decimal, total_events: int, bad_events: int) -> Decimal:
    """Fraction of the budget used: 0.5 is half, 1 is all of it, above 1 means the SLO is missed."""
    budget = error_budget(slo_percent, total_events)
    if budget == 0:
        raise ValueError("no events, so no budget to consume")
    return Decimal(bad_events) / budget


def burn_rate(slo_percent: str | Decimal, observed_error_percent: str | Decimal) -> Decimal:
    """Observed error rate divided by the error rate the SLO allows."""
    return Decimal(str(observed_error_percent)) / (Decimal(100) - _slo(slo_percent))


def days_to_exhaustion(window_days: int, rate: Decimal) -> Decimal | None:
    """At a constant burn rate, how long a full budget lasts; None when nothing is burning."""
    if rate <= 0:
        return None
    return Decimal(window_days) / rate


def release_allowed(slo_percent: str | Decimal, total_events: int, bad_events: int) -> bool:
    """The SRE book's rule: releases go out "as long as there is error budget remaining"."""
    return budget_consumed(slo_percent, total_events, bad_events) < 1
