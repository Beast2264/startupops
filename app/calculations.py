"""Pure calculation helpers — no I/O, fully unit-testable.

Every function that depends on "now" takes an explicit ``today`` argument so
tests are deterministic. The web layer passes ``date.today()``.
"""
from __future__ import annotations

from datetime import date
from typing import Optional


def days_until(target: Optional[date], today: date) -> Optional[int]:
    """Whole days from ``today`` to ``target``.

    Positive = future, negative = overdue/past, 0 = today, None if no target.
    """
    if target is None:
        return None
    return (target - today).days


def remaining_amount(
    actual_award: Optional[float], amount_used: Optional[float]
) -> Optional[float]:
    """Remaining credit = actual_award - amount_used.

    Returns None when there is no *actual* award yet. Remaining is NEVER
    derived from an advertised maximum — only from a real award.
    """
    if actual_award is None:
        return None
    used = amount_used or 0.0
    return round(actual_award - used, 2)


def percentage_remaining(
    actual_award: Optional[float], amount_used: Optional[float]
) -> Optional[float]:
    """Percentage of the actual award still available (0..100), or None."""
    if actual_award is None or actual_award <= 0:
        return None
    remaining = remaining_amount(actual_award, amount_used)
    if remaining is None:
        return None
    pct = (remaining / actual_award) * 100.0
    # Clamp to a sane display range.
    pct = max(0.0, min(100.0, pct))
    return round(pct, 1)


def expiration_bucket(
    expiration_date: Optional[date], today: date
) -> Optional[str]:
    """Classify how soon a credit expires.

    Returns one of: "EXPIRED", "30", "60", "90", "90_PLUS", or None.
    Buckets are cumulative-exclusive: "30" means <=30 days, "60" means
    31..60 days, "90" means 61..90 days.
    """
    days = days_until(expiration_date, today)
    if days is None:
        return None
    if days < 0:
        return "EXPIRED"
    if days <= 30:
        return "30"
    if days <= 60:
        return "60"
    if days <= 90:
        return "90"
    return "90_PLUS"


def within_days(target: Optional[date], days: int, today: date) -> bool:
    """True if ``target`` falls within the next ``days`` days (inclusive),
    and is not in the past."""
    d = days_until(target, today)
    if d is None:
        return False
    return 0 <= d <= days
