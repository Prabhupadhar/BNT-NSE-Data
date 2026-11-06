# Phase 1: Research and Architecture (NIFTY / BANKNIFTY options)

Status: **proposal, awaiting approval.** No trading code has been written. Nothing here is a
profitability claim. Every strategy must earn its place through the validation gates in §5.

Legend: **[V]** verified in a primary/official source or a reproducible API query on 2026-11-06.
**[R]** reported by secondary sources (blogs, forums, vendor pages). Treat as unverified until checked.

---

## 1. Reality check (read this first)

- **Base rate is hostile.** SEBI's FY2024-25 study found ~91% of individual traders in equity
  derivatives lost money, with net losses of ~₹1.06 lakh crore [R: Business Standard / Moneylife
  summaries of the SEBI study]. The project's default outcome should be "no strategy passes."
  A clean rejection is a successful result.
- **Costs are a large share of the risk budget.** At ₹50,000 with a 1% risk limit, the per-trade
  budget is ₹500. One NIFTY lot (65 qty, lot size per §3) at a ₹200 ATM premium is ₹13,000 of
  premium turnover. Round-trip brokerage, STT on the sell leg, exchange and SEBI charges, GST and
  a bid-ask spread of ₹0.5–1.0 per unit can easily cost ₹60–100 per lot round trip [assumption;
  must be calibrated against Kotak's actual schedule]. Costs are roughly 15–20% of the risk budget
  per trade, before slippage. This is the central constraint, and it is why most small-capital
  intraday option scalps fail.
- **Position sizing is coarse.** At 65 qty, ₹500 of risk means a stop of ~₹7.7 per unit premium.
  A ₹200 premium with a ₹7.7 stop is a ~4% stop, which is inside normal one-minute option noise.
  Expect stop-outs to dominate unless strikes are cheap or the stop is wider and the risk
  budget is larger. The plan must test this explicitly rather than assume it.
- **v1 is buy-only.** Option selling needs SPAN + exposure margin far above ₹50k and carries
  unbounded risk. Excluding it is a deliberate scope decision, not an oversight. Revisit only
  after a buy-side strategy passes.
- **Recommended angle, from the research:** the highest-probability edge in this space is less
  likely to be a new indicator than a *regime/filter* (when not to trade, which strike, what
  cost floor). Strategies should be tested as "signal + filter + cost-aware exit," not as bare
  indicator crossovers.

## 2. Open decisions (defaults chosen, change if you disagree)

| Decision | Default chosen | Why |
|---|---|---|
| Option side | Buy-only | Margin and risk are within ₹50k; selling is out of scope |
| Event engine | Custom, lean | Option-chain selection, Indian cost model and a veto-capable risk layer are needed regardless |
| Data budget | Assume ≤ ₹5k/month until a sample is validated | Vendor pricing is unverified; see §4 |
| Broker | Kotak Neo, paper-first | Per your spec |
| Persistence | Parquet + DuckDB; SQLite for paper-trade state | Single-user, local. Postgres only if live needs multi-process access |

## 3. Market and contract facts (must be config-driven, effective-dated)

- **Lot sizes:** NIFTY 65, BANKNIFTY 30 from Jan 2026 [R: multiple broker blogs; one source
  disagreed and was discarded]. Stored in `config/contracts.yaml` with `effective_from`, never
  hardcoded. Verify against the NSE circular before any sizing.
- **Expiries:** NIFTY weekly (Tuesday) plus monthly; BANKNIFTY monthly only (last Tuesday)
  [R]. Holiday shifts move expiry to the prior trading day. The expiry calendar is an input, not
  a rule in code.
- **SEBI retail algo framework (circular of 4 Feb 2025, amended Sept 2025)** [R]:
  - Algo orders are those placed/modified/cancelled by programs or broker APIs.
  - Individuals below 10 orders per second per exchange per segment are generally exempt from
    exchange registration.
  - Broker APIs require a vendor-specific API key and a **static IP whitelisted with the broker.**
    A cloud sandbox IP is not static, so live trading needs a fixed-IP host.
  - Brokers' rollout deadlines have been reported inconsistently (Jan 2026 vs Apr 2026).
    **Read the primary SEBI/NSE circulars before any live step.** This is a compliance gate, not
    an implementation detail.
- **Expiry-day risk:** gamma and premium decay concentrate on expiry, and intraday margin and
  position-limit rules tightened in 2024–25 [R; details to verify]. The risk engine must block
  or down-size expiry-day entries by default.

## 4. Data architecture

### 4.1 Source assessment

| Source | Use | Status |
|---|---|---|
| **Kotak Neo API** | Live quotes, order routing, instrument master | Official SDK repo exists (`Kotak-Neo/Kotak-neo-api-v2`). Historical candle endpoint **unverified**: an open issue reports 503s on `charts/v1/scrip/history`. A third-party adapter claims ~2 years of 1-min NIFTY data [R]. Must be probed before anything depends on it. |
| **Zerodha Kite Connect** | Index/futures history | Historical API covers **active** contracts only; expired NIFTY option history is not available via Kite Connect [R: Kite forum]. Ruled out for options history. |
| **Upstox** | Expired-instrument OHLC | Endpoint exists ("Get Expired Historical Candle Data") [V: docs title]; 1-min availability and plan restrictions reported [R]. Candidate. |
| **Dhan** | Rolling expired options history | Blog reports up to 5 years of 1–60 min data, ≤30 days per call, limited strikes around ATM [R]. Candidate; API is MIT-licensed open source (`dhan-oss/DhanHQ-py`). |
| **Global Datafeeds (NimbleDataPro)** | NSE F&O 1-min/EOD history | NSE-authorised vendor [R]; listed at ₹2,775/month for 1-month intraday history, API pricing by quote [R]. Candidate. |
| **TrueData** | NSE F&O history | NSE-authorised vendor [R]; pricing unclear and some plans exclude API access [R]. Candidate. |
| **NSE direct** | Daily F&O bhavcopy (OI, settlement), option chain | Official. Bhavcopy is the cleanest free source for daily OI validation. Enterprise/redistribution licensing: non-display F&O fee ~₹1.2 lakh/yr, with consent needed for redistribution [R: NSE pricing file]. Do **not** scrape the NSE website for production data (ToS and reliability). |
| **Self-recorded chain snapshots** | Bid/ask, IV, OI going forward | No historical bid-ask is reliably available. Recording chain snapshots from today onward is the only way to get real spread data. Start immediately once a source is approved. |

**Not usable:** `aeron7/nifty-banknifty-intraday-data` (101★, **no license**, 2023) and
forum "sell me data" offers. Unlicensed or unverifiable data cannot go into the research base.

### 4.2 Data policy

- Never forward-fill options bars across missing minutes; mark gaps and exclude or flag them.
- Store the **full strike universe including expired strikes** per expiry. Dropping strikes that
  later became illiquid or expired creates survivorship bias.
- Timestamps in IST, tz-aware, validated against the 09:15–15:30 session and holiday calendar.
- Options bars: OHLCV + OI where present. Bid/ask only where a source has it; otherwise the
  spread is **modelled** and the model is labelled in every trade record.
- IV and Greeks are computed in-house (Black-76 on futures for index options, or Black-Scholes
  with a documented rate/dividend assumption), with unit tests against known reference values.
  No vendor Greeks are trusted without a spot-check.

### 4.3 Storage layout

```
data/
  raw/<vendor>/<dataset>/<yyyy>/<mm>/...        # untouched vendor files, never edited
  parquet/bars_1m/symbol=NIFTY/date=YYYY-MM-DD/ # normalized, partitioned
  parquet/option_bars/underlying=.../expiry=.../
  parquet/chain_snapshots/...
  quality/<run_id>.json                          # per-load data quality report
```

DuckDB queries the Parquet directly; no ingestion into a DB file is needed for research.

## 5. Strategy evaluation methodology

### 5.1 Process per strategy (A–E, each independent, NIFTY and BANKNIFTY separately)

1. **Spec first.** Entry, exit, stop, target, time-exit, filters written in `docs/strategies/<X>.md`
   before any backtest. Parameter grid defined and frozen up front.
2. **Split.** Chronological only. Suggested: in-sample ≈ first 50% of history, validation ≈ next
   25% (used only to choose among a *small* grid), out-of-sample ≈ final 25% (touched once per
   frozen configuration). Walk-forward folds sized to ≥3 months each.
3. **Costs from day one.** Brokerage, STT, exchange transaction charges, SEBI fee, stamp duty,
   GST, modelled spread and slippage. Stress test at 1.5× and 2× slippage.
4. **Sensitivity.** Plateau, not a spike. If a ±10% parameter change flips expectancy sign, the
   strategy is curve-fit.
5. **Regime splits.** Trending vs sideways (e.g., ADX/efficiency ratio), high vs low volatility
   (ATR percentile), expiry vs non-expiry days, and year-by-year.
6. **Statistics.** Bootstrap the trade-level expectancy (confidence interval). Monte Carlo the trade
   sequence for drawdown distribution. Apply a multiple-testing correction across the grid (e.g.,
   Deflated Sharpe Ratio or White's Reality Check) because many configurations were tried.
7. **Decision.** Written pass/fail against §5.2 before looking at results.

### 5.2 Pass criteria (proposed, to be finalised before Phase 4)

- Net expectancy after full costs > 0 **out-of-sample**, and the bootstrap 95% CI lower bound > 0.
- ≥ 200 OOS trades per index per strategy. Fewer is "unknown," not "passed."
- Positive net result in a majority of walk-forward folds, with no single fold carrying the total.
- Still positive at 1.5× slippage. Failing at 2× is acceptable only if documented.
- Max drawdown within the risk budget at the configured position size.
- Failing any criterion = **rejected**, regardless of in-sample P&L.

### 5.3 Strategy-specific notes

- **A. ORB (9:15–9:30).** Few trades per day, so sample size is the risk. Test the retest
  variant separately from the plain breakout. Volume confirmation on index futures or spot is
  needed; index spot has no volume, so use futures volume.
- **B. VWAP + EMA(20/50).** Trend-following on 5-min with 15-min bias. Most likely to be
  cost-dominated; the filter matters more than the entry.
- **C. Price action / structure.** Hard to code objectively. Swing-point definitions must be
  causal (no look-ahead from later pivots). Include a precise pivot rule before testing.
- **D. Volatility breakout (BB squeeze / ATR expansion).** Breakouts on options are often
  overpriced after expansion. Test "buy the option on a volatility trigger" against "do nothing,"
  which is the honest baseline.
- **E. Options-specific.** Uses chain data, so it depends most on the data quality question in
  §4. Delta/strike selection and IV-rank filters need historical IV, which must be computed
  from consistent prices. Do not start E until data passes §4.2.

## 6. Architecture

```
            ┌──────────────┐   ┌───────────────┐
config/ ───►│ settings     │   │ contracts.yaml│ (lot sizes, expiries: effective-dated)
            └──────┬───────┘   └───────┬───────┘
                   ▼                   ▼
 vendors ─► ingest ─► normalize ─► quality checks ─► Parquet ──► DuckDB queries
 (adapters)                      (gaps, tz, expiry)              │
                                                                  ▼
                                                    features (VWAP, EMA, ATR, BB, IV, Greeks)
                                                                  │
                                                                  ▼
                                   strategies A–E  (pure functions: bars → signal intent)
                                                                  │  intent
                                                                  ▼
                                   ┌─────────── RISK ENGINE (may reject any intent) ───────────┐
                                   │ sizing by premium × lot, daily loss, trade caps, expiry  │
                                   └──────────────────────────────┬───────────────────────────┘
                                                                  ▼ approved orders
                         ┌────────────────────────┴───────────────────────────┐
                         ▼                                                    ▼
               Event backtester (costs, fills,                    Broker adapter
               spread, slippage, stops, trailing)                 ├─ PaperBroker (default)
                         │                                        └─ KotakNeoBroker (gated)
                         ▼                                                    │
              validation: IS/OOS, WFO, sensitivity,                       order state machine,
              Monte Carlo, bootstrap, regimes                         reconciliation, kill switch
                         │                                                    │
                         └──────────────► Streamlit dashboard ◄───────────────┘
```

Design rules:
- Strategies **never** place orders or read the broker. They emit intents.
- The risk engine is the only path to execution, and it can veto any intent with a logged reason.
- The same strategy code runs in backtest, paper and live. Only the broker adapter changes.
- Every config value that changes with the market (lots, expiries, charge rates, tax rates) is
  effective-dated and versioned.

### 6.1 Technology choices

| Choice | Pick | Reasoning / rejected alternative |
|---|---|---|
| Dataframes | **Polars** for pipeline, pandas only at library boundaries | Faster on large minute data; pandas is needed by VectorBT |
| Storage | **Parquet + DuckDB** | Columnar, cheap, fast analytical queries; Postgres deferred |
| Config | **Pydantic v2** + YAML | Typed validation of risk limits at load time |
| Backtester | **Custom event-driven** core; VectorBT for fast screens only | See §7 |
| Web API | **Defer FastAPI** | No service boundary in v1; Streamlit reads the library directly |
| Logging | structlog-style JSON | Trade logs must be machine-readable |
| Tests | pytest; property tests (hypothesis) for the cost model and sizing | Costs and sizing are where silent money errors live |
| Packaging | Docker after Phase 4 | Not needed for research |

## 7. Repository research

Metadata from the GitHub search API on 2026-11-06 (stars / forks / license / last push).
Repos not attached to this session could not be fetched directly; their numbers come from search
results.

| Repo | ★ / forks | License | Last push | Verdict |
|---|---|---|---|---|
| `nautechsystems/nautilus_trader` | 31,278 / 4,223 | LGPL-3.0 | 2026-11-06 | **Strongest event-driven engine.** Heavy to learn; no Kotak adapter. Keep as the fallback if the custom engine becomes the bottleneck. |
| `polakowo/vectorbt` | 9,695 / 1,259 | NOASSERTION | 2026-11-03 | Fast vectorised screening. **License must be checked** before depending on it. |
| `kernc/backtesting.py` | 9,199 / 1,576 | AGPL-3.0 | 2026-08-05 | Useful reference. AGPL is a poor fit for a private trading system; do not copy code. |
| `mementum/backtrader` | 23,669 / 5,323 | GPL-3.0 | 2024-08-19 | **Stale** (no push in 2+ years). Not recommended. |
| `dhan-oss/DhanHQ-py` | 216 / 158 | MIT | 2026-10-08 | Reference for a broker adapter pattern and expired-options endpoints. |
| `rajmaurya0904/bhav` | 27 / 5 | MIT | 2026-07-19 | NSE options backtester with an Indian cost model. **Reference only** for cost-model structure; verify its numbers independently. |
| `vikassharma545/Historical-Market-data-From-Zerodha` | 34 / 15 | MIT | 2026-10-01 | Zerodha historical downloader. Only useful for index/futures history given Kite limits. |
| `BarathGB007/nse-options-data-collector` | 17 / 8 | MIT | 2026-08-05 | Collects chain snapshots (OI, Greeks, bid/ask). Useful pattern for the forward-recording gap; still an NSE scraper, so treat as a pattern, not a dependency. |
| `marketcalls/openalgo-execution-skills` | 11 / 3 | MIT | 2026-04-28 | Possible broker-abstraction layer (OpenAlgo) that covers Kotak. Evaluate for the adapter; adds a dependency and attack surface. |
| `VarunS2002/Python-NSE-Option-Chain-Analyzer` | 671 / 268 | GPL-3.0 | 2026-05-22 | Popular but NSE scraper; GPL. Do not depend on it for production data. |
| `Kotak-Neo/Kotak-neo-api-v2` | not fetched | not checked | not checked | Official Kotak SDK. **Must be checked directly** (add repo to session) before Phase 7. |

**Reuse plan:** nothing is copied wholesale. Reuse candidates: cost-model structure (reference
bhav), broker adapter patterns (reference DhanHQ-py), snapshot recorder pattern (reference
BarathGB007). Everything else is implemented independently with tests.

## 8. Directory structure (proposed)

```
bnt-nse-data/
  config/
    settings.example.yaml        # capital, instruments, risk, timeframes (no secrets)
    contracts.yaml               # lot sizes, expiries: effective-dated
    charges.yaml                 # brokerage, STT, exchange, SEBI, stamp, GST: versioned
    strategies/{orb,vwap_ema,price_action,vol_breakout,options}.yaml
  src/bnt/
    data/        vendors/, ingest.py, normalize.py, quality.py, store.py
    instruments/ master.py, expiry.py, lots.py
    options/     iv.py, greeks.py, chain.py
    features/    vwap.py, ema.py, atr.py, bollinger.py, regime.py
    strategies/  base.py, orb.py, vwap_ema.py, price_action.py, vol_breakout.py, options_strat.py
    risk/        engine.py, sizing.py, rules.py
    costs/       charges.py, slippage.py
    backtest/    engine.py, fills.py, exits.py, trades.py, metrics.py
    validate/    splits.py, walk_forward.py, sensitivity.py, montecarlo.py, bootstrap.py, regimes.py
    broker/      base.py, paper.py, kotak_neo.py, orders.py (state machine), reconcile.py
    ops/         logging.py, killswitch.py, config.py
    dashboard/   app.py (Streamlit), pages/
  tests/         unit/ integration/ (mirrors src/bnt)
  docs/
    phase1-architecture.md
    strategies/  <one spec per strategy>
    data-quality/ <one report per dataset>
    dev-log.md
  Dockerfile, pyproject.toml, .github/workflows/ci.yml
```

## 9. Milestones

| # | Milestone | Exit gate |
|---|---|---|
| M0 | This document approved | Your explicit go-ahead |
| M1 | Data probes: Kotak history, Upstox/Dhan expired options, one vendor sample | Sample validated for gaps, tz, expiry mapping. Pick a source or stop. |
| M2 | Instrument master, expiry and lot calendar | Unit tests on holidays, lot-change dates, expiry shifts |
| M3 | Ingestion → Parquet → DuckDB, quality reports | Quality report per dataset; no silent gap filling |
| M4 | Options analytics (IV, Greeks) | Matches reference values within tolerance |
| M5 | Cost model + event backtester + Strategy A end-to-end | Cost model property tests; A run with full report |
| M6 | Strategies B–E on the same harness | Each has a frozen spec and a result |
| M7 | Validation suite (IS/OOS, WFO, sensitivity, MC, bootstrap, regimes) | Pass/fail decided per §5.2 |
| M8 | Risk engine with veto, wired into backtest | Tests: daily loss, caps, expiry block, no averaging down |
| M9 | Paper broker + Kotak read-only adapter | Reconciliation of paper fills vs replayed data |
| M10 | Streamlit dashboard | All seven pages on real backtest outputs |
| M11 | Paper trading | Minimum window (I suggest ≥ 8–12 weeks) before any live consideration |
| M12 | Live readiness review | Compliance (SEBI/NSE), static IP, kill switch, explicit human approval. **Not started by default.** |

Realistic timeline: M0–M7 is the research core. M11 is calendar-bound, not effort-bound.

## 10. Risks

**Financial**
- Costs and spread eat the edge at this capital level (§1). Most configurations will be negative.
- Stop-outs from normal noise at 65 qty with a ₹500 risk budget.
- Overfitting via many parameter tries. Mitigated by frozen specs and multiple-testing correction,
  but not eliminated.
- Expiry-day gamma and liquidity gaps; wide spreads on OTM strikes.
- Drawdown can exceed the 2% daily rule in a gap, since stops are not guaranteed fills.

**Data**
- No reliable historical bid-ask. Modelled spreads may be optimistic.
- Survivorship: expired strikes must be in the dataset.
- Vendor licensing for redistribution, and cost of a proper history.
- Kotak historical endpoint may not work as needed.

**Regulatory / operational**
- SEBI algo rules and timelines are inconsistently reported. Compliance review before live.
- Static-IP requirement for broker APIs; cloud sandboxes do not provide it.
- Broker API rate limits and outages. Retry and reconciliation are required, not optional.
- Kill-switch and order-state recovery after a crash mid-session.

**Process**
- Scope creep into five strategies × two indices × many parameters at once. Enforce
  the brief's rule: each strategy is evaluated independently before any combination.
- The most likely failure mode is a strategy that looks great in-sample and is never honestly
  tested out-of-sample. The gates in §5 exist to make that impossible to hide.

## 11. What is unverified (must check before Phase 2)

1. Kotak Neo historical candle endpoint: works? which intervals, how far back, is it options?
2. Kotak Neo brokerage schedule, current STT/exchange/SEBI/GST rates used in the cost model.
3. NSE lot-size and expiry circulars for the current period (secondary sources only so far).
4. SEBI retail-algo circular text and the applicable deadlines.
5. Current vendor pricing and API terms (Global Datafeeds, TrueData, Dhan, Upstox).
6. VectorBT license terms (GitHub reports NOASSERTION).
7. Kotak official SDK repo metadata and API terms.
