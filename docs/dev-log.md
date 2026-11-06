# Development log

## 2026-11-06: Phase 2 (partial)

Approved design: `docs/phase1-architecture.md`.

Done (tests passing, 12/12, synthetic fixtures only):
- Project skeleton (`pyproject.toml`, `src/bnt`, `tests/`).
- `config/contracts.yaml` with effective-dated lot sizes. Entries are marked `verified: false`.
- Expiry calendar: NIFTY weekly and monthly, BANKNIFTY monthly, holiday shift to prior trading day.
  Holiday list is an input. **No official NSE holiday list has been loaded yet.**
- Bar quality checks: timezone, nulls, duplicates, OHLC ordering, negative volume, session window, gap
  reporting. Gaps are reported and never filled.
- Parquet partitions (`bars_<N>m/symbol=/date=`) with idempotent rewrites, and DuckDB queries over them.

Not done, and blocked:
- **M1 data probes.** Needs Kotak Neo API credentials for the historical endpoint, plus a
  vendor decision (Global Datafeeds, TrueData, Dhan, or Upstox) and a funded sample. Not attempted.
- **Official NSE holiday list and lot-size circular.** Needed before any real sizing or expiry use.
- **Ingestion adapters.** Depend on M1.

Decisions taken on defaults (change if wrong):
- Lot-size change dates use the secondary-source "Jan 2026" date, because sources conflict.
- Expiry weekdays are reported values (NIFTY weekly Tuesday, BANKNIFTY monthly Tuesday).
