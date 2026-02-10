# Alice Autopilot Plan

## Objective
Find ETF strategy variants that beat buy_and_hold across a universe of ~59 ETFs.

**"Beat" definition:** A variant beats buy_hold if:
- Its `mean(cagr_pct)` across all 59 ETFs > baseline avg CAGR (6.08%), **OR**
- Its `mean(sharpe)` across all 59 ETFs > baseline avg Sharpe (0.39)

## How It Works
1. Each cron wakeup runs ONE job via `run_job.py`
2. Each job writes a **plan file** (before) and **result file** (after) in `result/alice_checking/`
3. After completing, schedules next wakeup in 1 minute
4. Jobs numbered sequentially: 001, 002, 003, ...
5. User tracks progress in `alice_checking/progress.md`

## Current State
Check `result/alice_checking/` for `job-result-*.md` files to see what's done.

## Reference Files (read these first)

| File | Purpose |
|------|---------|
| `alice_checking/job_buy_hold.py` | Job 001 -- pattern reference for all jobs |
| `alice_checking/job_strategy_batch.py` | Jobs 002-013 -- runs variant grid for one strategy family |
| `alice_checking/compare_utils.py` | Shared helpers for compare_result.md (scoreboard markers, formatters) |
| `checking/tool_run_variants_grid.py` | Parameter grids -- `build_variants()` is source of truth for variant defs |
| `checking/strategy_backtest_lib.py` | All strategy functions + `compute_metrics()` |

## Job Queue

| Job | Script | Strategy Family |
|-----|--------|-----------------|
| 001 | job_buy_hold.py | buy_hold (baseline) |
| 002 | job_strategy_batch.py --family sma --job-id 002 | strat_sma_crossover |
| 003 | job_strategy_batch.py --family ema --job-id 003 | strat_ema_crossover |
| 004 | job_strategy_batch.py --family momentum --job-id 004 | strat_momentum |
| 005 | job_strategy_batch.py --family rsi --job-id 005 | strat_rsi_mean_reversion |
| 006 | job_strategy_batch.py --family bollinger --job-id 006 | strat_bollinger_mean_reversion |
| 007 | job_strategy_batch.py --family donchian --job-id 007 | strat_donchian |
| 008 | job_strategy_batch.py --family macd --job-id 008 | strat_macd_crossover |
| 009 | job_strategy_batch.py --family keltner --job-id 009 | strat_keltner_breakout |
| 010 | job_strategy_batch.py --family stochrsi --job-id 010 | strat_stochrsi_mean_reversion |
| 011 | job_strategy_batch.py --family vol_target --job-id 011 | strat_vol_targeting |
| 012 | job_strategy_batch.py --family crash_filter --job-id 012 | strat_crash_filter_drawdown |
| 013 | job_strategy_batch.py --family trend_filter --job-id 013 | strat_trend_filter |
| 014 | job_winners_summary.py | Compile all winners |

## How to Run
```bash
cd /home/zoftdev/clawd/workspace/etf

# Run a single job manually
uv run python alice_checking/job_buy_hold.py

# Run a strategy batch manually
uv run python alice_checking/job_strategy_batch.py --family sma --job-id 002

# Or use the dispatcher (runs next pending job + schedules crontab)
uv run python alice_checking/run_job.py
```

## job_strategy_batch.py Blueprint

This script handles jobs 002-013. It:
1. Accepts `--family` (e.g. sma, ema, momentum) and `--job-id` (e.g. 002)
2. Imports variant definitions from `checking/tool_run_variants_grid.py`'s `build_variants()`
3. Filters variants by family prefix (see mapping below)
4. Loads `buy_hold_baseline.csv` to get baseline thresholds
5. Fetches 20 years of OHLCV data for all ETFs
6. Runs all filtered variants x all ETFs via ProcessPoolExecutor (parallelized by ETF)
7. Compares each variant's avg metrics against baseline
8. Writes plan/result files and updates `compare_result.md`

### Family-to-Prefix Mapping
```
sma          -> "sma_"
ema          -> "ema_"
momentum     -> "mom_"
rsi          -> "rsi_"
bollinger    -> "boll_"
donchian     -> "donch_"
macd         -> "macd_"
keltner      -> "kelt_"       !! SPECIAL: needs OHLC DataFrame, not just Close
stochrsi     -> "stochrsi_"
vol_target   -> "vol_"
crash_filter -> "crash_"
trend_filter -> "trend_"
```

### Keltner Special Case (Job 009)
`strat_keltner_breakout()` requires a full OHLC DataFrame (`df`), not just Close series.
The worker function passes `df` (with High/Low/Close columns) to Keltner variants.
All other strategies receive only `close` (pd.Series).
This is handled automatically in `job_strategy_batch.py`.

## Data Sources (read-only, never modify)
- `core/etf_data_fetcher.py` -- ETFDataFetcher class for fetching OHLCV data
- `data/etf-v3.yaml` -- ETF universe (~59 ETFs)

## File Output Convention
```
result/alice_checking/
    compare_result.md             # SHARED -- scoreboard + per-job sections
    job-plan-{ID}-{NAME}.md       # written before job runs
    job-result-{ID}-{NAME}.md     # written after job completes
    buy_hold_baseline.csv         # job 001 output (reused by all others)
    {family}_results.csv          # per-job detailed CSV (all variants x all ETFs)
```

### compare_result.md Structure
```
# Compare Result

## Baseline Thresholds (Job 001: buy_hold)
[table with avg_cagr, avg_sharpe thresholds]

## Scoreboard: All Winners
<!-- SCOREBOARD_START -->
| variant | family | avg_cagr | avg_sharpe | avg_mdd | beat_cagr | beat_sharpe | job |
|---------|--------|----------|------------|---------|-----------|-------------|-----|
[winner rows inserted here by each job]
<!-- SCOREBOARD_END -->

---

## Job 001: buy_hold (baseline)
[per-job detail section]

## Job 002: sma
[per-job detail section]
...
```

Every job MUST:
1. Insert winner rows into the scoreboard (between `SCOREBOARD_START`/`SCOREBOARD_END` markers)
2. Append a per-job detail section at the bottom

### Standardized Winner Row
```
| variant | family | avg_cagr | avg_sharpe | avg_mdd | beat_cagr | beat_sharpe | job |
```
- `beat_cagr` = "Y" if variant avg_cagr > baseline avg_cagr, else "-"
- `beat_sharpe` = "Y" if variant avg_sharpe > baseline avg_sharpe, else "-"

Use `alice_checking/compare_utils.py` helpers: `append_winners_to_scoreboard()` and `append_job_section()`.

## Rules
- All code lives in `alice_checking/` -- reference `job_buy_hold.py` for the pattern
- NEVER modify files outside `alice_checking/` and `result/alice_checking/`
- ALWAYS read `buy_hold_baseline.csv` for comparison (don't re-run buy_hold)
- ALWAYS create plan + result files for every job
- ALWAYS update `compare_result.md` (scoreboard + job section)
- If a job fails, log the error in result file and move to next job
- Keep `progress.md` updated after each job
