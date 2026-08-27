# BNT-NSE-Data

Research dataset of NSE index option chain snapshots (NIFTY, BANKNIFTY).

**This is data collection only.** No order placement, no broker integration,
no trading logic lives in this repo.

## Status

Step 1 of the build: single-snapshot fetch and summary. Storage (Parquet),
scheduling (GitHub Actions), and the full schema documentation are not built yet.

## Setup

```bash
pip install -r requirements.txt
```

## Fetch one snapshot

```bash
python fetch_one.py            # BANKNIFTY
python fetch_one.py NIFTY
```

Prints spot price, strike count, expiries, rows per expiry, and sample
near-the-money rows. Nothing is written to disk yet.

## Tests

Offline tests — parser and retry logic against a saved payload shape,
no network needed:

```bash
python -m unittest discover -s tests -v
```

## How the NSE fetch works

NSE's `/api/option-chain-indices` returns 403 to clients without cookies from
the main site. `collector/nse_client.py` therefore:

1. visits `nseindia.com` and `/option-chain` with browser-like headers to collect cookies,
2. calls the API with those cookies and a `Referer` header,
3. re-primes cookies automatically on 401/403, backs off on 429, and retries
   network errors with exponential backoff,
4. treats an HTML block page or an empty chain as a failure rather than as data.

All timestamps use `Asia/Kolkata`, never the machine's local timezone.
