"""Bar-level data quality checks. Reports problems; never repairs data silently."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

import polars as pl

TZ = "Asia/Kolkata"
SESSION_OPEN = time(9, 15)
SESSION_LAST_BAR_START = time(15, 29)  # bars are labelled by their start time
REQUIRED_COLUMNS = ["ts", "open", "high", "low", "close", "volume"]


@dataclass
class QualityReport:
    rows: int
    hard_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_bars: dict[str, int] = field(default_factory=dict)  # ISO date -> missing count

    @property
    def passed(self) -> bool:
        return not self.hard_errors


def _expected_grid(day: date, interval_min: int) -> list[datetime]:
    step = timedelta(minutes=interval_min)
    t = datetime.combine(day, SESSION_OPEN)
    last = datetime.combine(day, SESSION_LAST_BAR_START)
    out = []
    while t <= last:
        out.append(t)
        t += step
    return out


def check_bars(df: pl.DataFrame, interval_min: int) -> QualityReport:
    report = QualityReport(rows=df.height)

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        report.hard_errors.append(f"missing columns: {missing_cols}")
        return report
    if df.height == 0:
        report.warnings.append("empty frame")
        return report

    ts_dtype = df.schema["ts"]
    tz = getattr(ts_dtype, "time_zone", None)
    if tz != TZ:
        report.hard_errors.append(f"ts must be tz-aware {TZ}, got {tz}")
        return report

    null_counts = df.select(pl.col(["open", "high", "low", "close", "volume"]).null_count()).row(0)
    if any(n > 0 for n in null_counts):
        report.hard_errors.append(f"null values in OHLCV: {null_counts}")

    dups = df.height - df["ts"].n_unique()
    if dups:
        report.hard_errors.append(f"{dups} duplicate timestamps")

    bad_ohlc = df.filter(
        (pl.col("high") < pl.max_horizontal("open", "close", "low"))
        | (pl.col("low") > pl.min_horizontal("open", "close", "high"))
    ).height
    if bad_ohlc:
        report.hard_errors.append(f"{bad_ohlc} bars violate OHLC ordering")

    neg_vol = df.filter(pl.col("volume") < 0).height
    if neg_vol:
        report.hard_errors.append(f"{neg_vol} bars with negative volume")

    tod = pl.col("ts").dt.time()
    off_session = df.filter((tod < SESSION_OPEN) | (tod > SESSION_LAST_BAR_START)).height
    if off_session:
        report.hard_errors.append(f"{off_session} bars outside the 09:15-15:29 session")

    if not df["ts"].is_sorted():
        report.warnings.append("input was not sorted by ts")

    # Gap detection on naive IST wall-clock times (the session is defined in IST).
    present = set(df["ts"].dt.replace_time_zone(None).to_list())
    for day in sorted(set(df["ts"].dt.date().to_list())):
        n_missing = sum(1 for t in _expected_grid(day, interval_min) if t not in present)
        if n_missing:
            report.missing_bars[str(day)] = n_missing
    if report.missing_bars:
        report.warnings.append(f"gaps on {len(report.missing_bars)} day(s); gaps are NOT filled")
    return report
