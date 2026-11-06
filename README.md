# BNT-NSE-Data

Research and paper-trading system for NIFTY / BANKNIFTY options. Live trading is disabled
by default and requires explicit authorization. See `docs/phase1-architecture.md` for the design.

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Layout

- `config/contracts.yaml` - effective-dated lot sizes and expiry rules (`verified: false` entries need checking)
- `src/bnt/config.py` - typed config loader
- `src/bnt/instruments/calendar.py` - lot-size lookup and expiry calendar
- `src/bnt/data/quality.py` - bar quality checks (reports gaps, never fills them)
- `src/bnt/data/store.py` - Parquet partitions and DuckDB queries
- `docs/dev-log.md` - development log and open blockers

No market data is included. Tests use synthetic fixtures generated in code.
