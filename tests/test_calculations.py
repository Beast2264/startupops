"""Pure calculation helpers: remaining, percentage, days, expiration windows."""
from datetime import date

from app import calculations as calc

TODAY = date(2026, 8, 16)


def test_remaining_amount_from_actual_award_only():
    assert calc.remaining_amount(1000.0, 250.0) == 750.0


def test_remaining_none_without_actual_award():
    # Remaining must never be derived from an advertised maximum.
    assert calc.remaining_amount(None, 0.0) is None


def test_remaining_defaults_used_to_zero():
    assert calc.remaining_amount(500.0, None) == 500.0


def test_percentage_remaining():
    assert calc.percentage_remaining(1000.0, 250.0) == 75.0


def test_percentage_none_without_award():
    assert calc.percentage_remaining(None, 10.0) is None


def test_days_until_future_and_past():
    assert calc.days_until(date(2026, 8, 26), TODAY) == 10
    assert calc.days_until(date(2026, 8, 6), TODAY) == -10
    assert calc.days_until(TODAY, TODAY) == 0
    assert calc.days_until(None, TODAY) is None


def test_expiration_buckets():
    assert calc.expiration_bucket(date(2026, 8, 1), TODAY) == "EXPIRED"
    assert calc.expiration_bucket(date(2026, 9, 10), TODAY) == "30"   # 25 days
    assert calc.expiration_bucket(date(2026, 10, 10), TODAY) == "60"  # 55 days
    assert calc.expiration_bucket(date(2026, 11, 10), TODAY) == "90"  # 86 days
    assert calc.expiration_bucket(date(2027, 1, 1), TODAY) == "90_PLUS"
    assert calc.expiration_bucket(None, TODAY) is None


def test_within_days():
    assert calc.within_days(date(2026, 9, 11), 30, TODAY) is True   # 26 days
    assert calc.within_days(date(2026, 12, 1), 30, TODAY) is False
    assert calc.within_days(date(2026, 8, 1), 30, TODAY) is False   # past
    assert calc.within_days(None, 30, TODAY) is False
