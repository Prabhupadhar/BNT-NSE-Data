#!/usr/bin/env python3
"""Fetch ONE option chain snapshot and print a summary.

Usage:
    python fetch_one.py              # BANKNIFTY
    python fetch_one.py NIFTY
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime

import pandas as pd

from collector.nse_client import IST, NSEError, fetch_snapshot


def main(symbol: str = "BANKNIFTY") -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    print(f"Fetching {symbol} option chain at "
          f"{datetime.now(IST):%Y-%m-%d %H:%M:%S %Z} ...\n")

    try:
        rows = fetch_snapshot(symbol)
    except NSEError as exc:
        print(f"FAILED: {exc}")
        return 1

    df = pd.DataFrame(rows)

    print("=" * 68)
    print(f"  {symbol} SNAPSHOT")
    print("=" * 68)
    print(f"  Collected at (IST) : {df['collected_at_ist'].iloc[0]:%Y-%m-%d %H:%M:%S}")
    print(f"  NSE timestamp      : {df['nse_timestamp'].iloc[0]}")
    print(f"  Spot (underlying)  : {df['spot'].iloc[0]}")
    print(f"  Total rows         : {len(df):,}")
    print(f"  Unique strikes     : {df['strike_price'].nunique()}")
    print(f"  Strike range       : {df['strike_price'].min():,.0f} "
          f".. {df['strike_price'].max():,.0f}")
    print(f"  Expiries ({df['expiry_date'].nunique()})       : "
          f"{', '.join(df['expiry_date'].unique()[:8])}")
    print(f"  CE rows / PE rows  : "
          f"{(df['option_type'] == 'CE').sum()} / {(df['option_type'] == 'PE').sum()}")
    print("=" * 68)

    # Rows per expiry, so it is obvious nothing was filtered out.
    print("\nRows per expiry:")
    print(df.groupby("expiry_date", sort=False).size().to_string())

    # Sample near-the-money rows from the nearest expiry.
    spot = df["spot"].iloc[0]
    nearest = df["expiry_date"].iloc[0]
    sample = (
        df[df["expiry_date"] == nearest]
        .assign(dist=lambda d: (d["strike_price"] - spot).abs())
        .sort_values(["dist", "option_type"])
        .head(10)
        .drop(columns="dist")
    )
    cols = ["expiry_date", "strike_price", "option_type", "lastPrice",
            "impliedVolatility", "openInterest", "changeinOpenInterest",
            "totalTradedVolume", "bidQty", "bidprice", "askPrice", "askQty"]
    print(f"\nSample rows nearest the money (expiry {nearest}):")
    with pd.option_context("display.width", 200, "display.max_columns", None):
        print(sample[cols].to_string(index=False))

    print(f"\nAll columns captured ({len(df.columns)}):")
    print("  " + ", ".join(df.columns))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "BANKNIFTY"))
