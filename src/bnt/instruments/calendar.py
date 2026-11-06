"""Lot-size lookup and expiry calendar. Pure functions, no I/O."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from bnt.config import WEEKDAY_INDEX, ContractsConfig


@dataclass(frozen=True)
class Expiry:
    expiry_date: date
    kind: str  # "weekly" or "monthly"


def lot_size(cfg: ContractsConfig, underlying: str, on: date) -> int:
    """Lot size in force on `on`. Raises if no entry covers that date."""
    entries = cfg.spec(underlying).lot_sizes
    covering = [e for e in entries if e.effective_from <= on]
    if not covering:
        raise ValueError(f"no lot size for {underlying} on {on}")
    return covering[-1].lot_size


def _previous_trading_day(d: date, holidays: frozenset[date]) -> date:
    while d.weekday() >= 5 or d in holidays:
        d -= timedelta(days=1)
    return d


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    d = nxt - timedelta(days=1)
    while d.weekday() != weekday:
        d -= timedelta(days=1)
    return d


def _weekdays(start: date, end: date, weekday: int) -> Iterable[date]:
    d = start + timedelta(days=(weekday - start.weekday()) % 7)
    while d <= end:
        yield d
        d += timedelta(days=7)


def expiries(
    cfg: ContractsConfig,
    underlying: str,
    start: date,
    end: date,
    holidays: Iterable[date] = (),
) -> list[Expiry]:
    """Expiry dates in [start, end]. Holidays/weekends shift expiry to the prior trading day.

    The holiday list must come from the official NSE calendar. An empty list is NOT
    a valid production input, it only makes tests readable.
    """
    spec = cfg.spec(underlying)
    hol = frozenset(holidays)
    found: dict[date, str] = {}

    for y in range(start.year, end.year + 1):
        for m in range(1, 13):
            raw = _last_weekday_of_month(y, m, WEEKDAY_INDEX[spec.monthly_weekday])
            d = _previous_trading_day(raw, hol)
            if start <= d <= end:
                found[d] = "monthly"

    if spec.has_weekly:
        assert spec.weekly_weekday is not None
        for raw in _weekdays(start, end, WEEKDAY_INDEX[spec.weekly_weekday]):
            d = _previous_trading_day(raw, hol)
            if start <= d <= end:
                found.setdefault(d, "weekly")

    return [Expiry(d, k) for d, k in sorted(found.items())]
