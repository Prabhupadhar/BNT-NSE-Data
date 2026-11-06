"""Parquet storage for normalized bars, queried with DuckDB.

Layout: <root>/bars_<N>m/symbol=<SYM>/date=<YYYY-MM-DD>/part.parquet
Writes are idempotent per partition (a re-run overwrites that day's file).
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl


def write_bars(df: pl.DataFrame, root: str | Path, symbol: str, interval_min: int) -> list[Path]:
    base = Path(root) / f"bars_{interval_min}m" / f"symbol={symbol}"
    written: list[Path] = []
    frame = df.with_columns(pl.col("ts").dt.date().alias("_day"))
    for (day,), part in frame.group_by(["_day"], maintain_order=True):
        out_dir = base / f"date={day}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "part.parquet"
        part.drop("_day").write_parquet(out)
        written.append(out)
    return written


def query(sql: str, root: str | Path, interval_min: int) -> pl.DataFrame:
    """Run SQL against all bars for one interval. The table is named `bars`."""
    glob = str(Path(root) / f"bars_{interval_min}m" / "*" / "*" / "*.parquet")
    con = duckdb.connect()
    try:
        escaped = glob.replace("'", "''")  # DuckDB cannot bind params in CREATE VIEW
        con.execute(
            f"CREATE VIEW bars AS SELECT * FROM read_parquet('{escaped}', hive_partitioning=true)"
        )
        return pl.from_arrow(con.sql(sql).to_arrow_table())
    finally:
        con.close()
