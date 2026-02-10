# Alice Autopilot Plan

## Objective
Find ETF strategy variants that beat buy_and_hold.
"Beat" = higher avg CAGR **OR** higher avg Sharpe across all ETFs.

## How It Works
1. Each cron wakeup runs ONE job via `run_job.py`
2. Each job writes a **plan file** (before) and **result file** (after) in `result/alice_checking/`
3. After completing, schedules next wakeup in 1 minute
4. Jobs numbered sequentially: 001, 002, 003, ...
5. User tracks progress in `alice_checking/progress.md`

## Current State
Check `result/alice_checking/` for `job-result-*.md` files to see what's done.

## Job Queue

| Job | Script | Strategy Family |
|-----|--------|-----------------|
| 001 | job_buy_hold.py | buy_hold (baseline) |
| 002 | job_strategy_batch.py --family sma | strat_sma_crossover |
| 003 | job_strategy_batch.py --family ema | strat_ema_crossover |
| 004 | job_strategy_batch.py --family momentum | strat_momentum |
| 005 | job_strategy_batch.py --family rsi | strat_rsi_mean_reversion |
| 006 | job_strategy_batch.py --family bollinger | strat_bollinger_mean_reversion |
| 007 | job_strategy_batch.py --family donchian | strat_donchian |
| 008 | job_strategy_batch.py --family macd | strat_macd_crossover |
| 009 | job_strategy_batch.py --family keltner | strat_keltner_breakout |
| 010 | job_strategy_batch.py --family stochrsi | strat_stochrsi_mean_reversion |
| 011 | job_strategy_batch.py --family vol_target | strat_vol_targeting |
| 012 | job_strategy_batch.py --family crash_filter | strat_crash_filter_drawdown |
| 013 | job_strategy_batch.py --family trend_filter | strat_trend_filter |
| 014 | job_winners_summary.py | Compile all winners |

## How to Run
```bash
cd /home/zoftdev/clawd/workspace/etf

# Run a single job manually
uv run python alice_checking/job_buy_hold.py

# Or use the dispatcher (runs next pending job + schedules crontab)
uv run python alice_checking/run_job.py
```

## Job Pattern (follow job_buy_hold.py as reference)

Every job script follows this template:
1. `project_root = Path(__file__).resolve().parent.parent`
2. `sys.path.insert(0, str(project_root))`
3. Import from `core.etf_data_fetcher` and `checking.strategy_backtest_lib`
4. Use `ETFDataFetcher(yaml_path="data/etf-v3.yaml")`
5. Write **job-plan** file BEFORE running
6. `ProcessPoolExecutor` for parallel ETF processing
7. Compare results vs buy_hold baseline (from `buy_hold_baseline.csv`)
8. Write **job-result** file AFTER running with summary stats

## Key Libraries (read-only, never modify)
- `core/etf_data_fetcher.py` -- ETFDataFetcher class for fetching OHLCV data
- `checking/strategy_backtest_lib.py` -- all strategy functions + compute_metrics
- `checking/tool_view_verify_hold_etf.py` -- get_group_lv2 helper
- `data/etf-v3.yaml` -- ETF universe (~60 ETFs)

## File Output Convention
```
result/alice_checking/
    compare_result.md             # ★ SHARED across all jobs - each job appends its section
    job-plan-{ID}-{NAME}.md       # written before job runs
    job-result-{ID}-{NAME}.md     # written after job completes
    buy_hold_baseline.csv         # job 001 output (reused by all others)
    {name}_results.csv            # per-job detailed CSV
```

### compare_result.md (cross-job summary)
Every job MUST append a section to `compare_result.md`. This is the **main file** for tracking
which variants beat buy_hold across all jobs. Each section can have variant-specific tables,
notes, or any unstructured content relevant to that job's findings.

## Rules
- NEVER modify files in `core/` or `checking/` -- those are shared libraries
- ALWAYS read `buy_hold_baseline.csv` for comparison (don't re-run buy_hold)
- ALWAYS create plan + result files for every job
- If a job fails, log the error in result file and move to next job
- Keep `progress.md` updated after each job
