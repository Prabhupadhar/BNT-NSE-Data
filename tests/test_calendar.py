"""Lot-size and expiry calendar tests. Uses the repo's contracts.yaml."""
from datetime import date
from pathlib import Path

import pytest

from bnt.config import load_contracts
from bnt.instruments.calendar import expiries, lot_size

CFG = load_contracts(Path(__file__).resolve().parents[1] / "config" / "contracts.yaml")


def test_lot_size_switches_on_effective_date():
    assert lot_size(CFG, "NIFTY", date(2025, 12, 31)) == 75
    assert lot_size(CFG, "NIFTY", date(2026, 1, 1)) == 65
    assert lot_size(CFG, "BANKNIFTY", date(2025, 6, 2)) == 35
    assert lot_size(CFG, "BANKNIFTY", date(2026, 1, 1)) == 30


def test_lot_size_unknown_underlying_fails_closed():
    with pytest.raises(KeyError):
        lot_size(CFG, "FINNIFTY", date(2026, 1, 1))


def test_banknifty_has_no_weekly_expiries():
    exps = expiries(CFG, "BANKNIFTY", date(2026, 1, 1), date(2026, 3, 31))
    assert all(e.kind == "monthly" for e in exps)
    assert len(exps) == 3


def test_nifty_weekly_are_tuesdays_and_monthly_is_last_tuesday():
    exps = expiries(CFG, "NIFTY", date(2026, 1, 1), date(2026, 1, 31))
    assert all(e.expiry_date.weekday() == 1 for e in exps)
    monthly = [e for e in exps if e.kind == "monthly"]
    assert [e.expiry_date for e in monthly] == [date(2026, 1, 27)]
    # 6, 13, 20, 27 Jan 2026 are Tuesdays; 27th is the monthly and must not be duplicated.
    assert len(exps) == 4


def test_holiday_shifts_expiry_to_previous_trading_day():
    # Tuesday 27 Jan 2026 is a holiday -> monthly moves to Monday 26 Jan.
    exps = expiries(CFG, "NIFTY", date(2026, 1, 1), date(2026, 1, 31), holidays=[date(2026, 1, 27)])
    monthly = [e for e in exps if e.kind == "monthly"]
    assert monthly[0].expiry_date == date(2026, 1, 26)
