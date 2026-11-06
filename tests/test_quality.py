"""Data quality checks on SYNTHETIC bars (test fixtures, not market data)."""
from datetime import date, datetime, timedelta

import polars as pl

from bnt.data.quality import check_bars


def synthetic_day(day: date, minutes: int = 375, interval: int = 1) -> pl.DataFrame:
    start = datetime.combine(day, datetime.min.time()).replace(hour=9, minute=15)
    rows = []
    for i in range(0, minutes, interval):
        t = start + timedelta(minutes=i)
        rows.append({"ts": t, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 10})
    df = pl.DataFrame(rows)
    return df.with_columns(pl.col("ts").dt.replace_time_zone("Asia/Kolkata"))


def test_clean_day_passes_with_no_gaps():
    report = check_bars(synthetic_day(date(2026, 1, 5)), interval_min=1)
    assert report.passed, report.hard_errors
    assert report.missing_bars == {}


def test_gap_is_reported_not_filled():
    df = synthetic_day(date(2026, 1, 5)).filter(pl.col("ts").dt.hour().ne(9) | pl.col("ts").dt.minute().ne(30))
    report = check_bars(df, interval_min=1)
    assert report.passed
    assert report.missing_bars == {"2026-01-05": 1}
    assert df.height == 374  # no rows were added


def test_duplicate_timestamp_is_hard_error():
    df = pl.concat([synthetic_day(date(2026, 1, 5)), synthetic_day(date(2026, 1, 5)).head(1)])
    assert not check_bars(df, interval_min=1).passed


def test_ohlc_violation_is_hard_error():
    df = synthetic_day(date(2026, 1, 5)).with_columns(
        pl.when(pl.col("ts").dt.minute() == 20).then(pl.lit(102.0)).otherwise(pl.col("low")).alias("low")
    )
    assert not check_bars(df, interval_min=1).passed


def test_naive_timestamps_are_rejected():
    df = synthetic_day(date(2026, 1, 5)).with_columns(pl.col("ts").dt.replace_time_zone(None))
    report = check_bars(df, interval_min=1)
    assert not report.passed
