from decimal import Decimal

import pytest
from fundamentals.slo_budget import (
    budget_consumed,
    burn_rate,
    days_to_exhaustion,
    error_budget,
    release_allowed,
)

pytestmark = pytest.mark.exercise


def test_workbook_example():
    # Google SRE workbook: 99.9% over 3 million requests -> 3,000 errors; 1,500 errors cost 50%.
    assert error_budget("99.9", 3_000_000) == Decimal(3000)
    assert budget_consumed("99.9", 3_000_000, 1_500) == Decimal("0.5")


def test_exact_decimals():
    assert error_budget("99.95", 20_000) == Decimal(10)
    assert error_budget(Decimal("99"), 250) == Decimal("2.5")


def test_burn_rate_of_one():
    assert burn_rate("99.9", "0.1") == Decimal(1)
    assert burn_rate("99.9", "1.44") == Decimal("14.4")
    assert burn_rate("99.9", "0") == Decimal(0)


def test_days_to_exhaustion():
    assert days_to_exhaustion(30, Decimal(1)) == Decimal(30)
    assert days_to_exhaustion(30, Decimal(6)) == Decimal(5)
    assert days_to_exhaustion(30, Decimal(0)) is None


def test_release_rule():
    assert release_allowed("99.9", 20_000, 19) is True
    assert release_allowed("99.9", 20_000, 20) is False
    assert release_allowed("99.9", 20_000, 30) is False
    assert budget_consumed("99.9", 20_000, 30) == Decimal("1.5")


def test_invalid_slos():
    for bad in ("100", "0", "101"):
        with pytest.raises(ValueError):
            error_budget(bad, 1000)
    with pytest.raises(ValueError):
        error_budget("99.9", -1)
    with pytest.raises(ValueError):
        budget_consumed("99.9", 0, 0)
