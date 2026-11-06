"""Round-trip test for Parquet partitions + DuckDB queries (synthetic data)."""
from datetime import date

import polars as pl

from bnt.data.store import query, write_bars
from tests.test_quality import synthetic_day


def test_write_then_query_roundtrip(tmp_path):
    df = pl.concat([synthetic_day(date(2026, 1, 5)), synthetic_day(date(2026, 1, 6))])
    files = write_bars(df, tmp_path, symbol="NIFTY", interval_min=1)
    assert len(files) == 2
    out = query("SELECT count(*) AS n FROM bars", tmp_path, interval_min=1)
    assert out["n"][0] == df.height


def test_rewrite_is_idempotent(tmp_path):
    df = synthetic_day(date(2026, 1, 5))
    write_bars(df, tmp_path, symbol="NIFTY", interval_min=1)
    write_bars(df, tmp_path, symbol="NIFTY", interval_min=1)
    out = query("SELECT count(*) AS n FROM bars", tmp_path, interval_min=1)
    assert out["n"][0] == df.height
