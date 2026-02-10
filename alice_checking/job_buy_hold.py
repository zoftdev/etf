"""job_buy_hold.py -- Job 001: Buy & Hold baseline for all ETFs.

Runs buy_and_hold on every ETF in data/etf-v3.yaml using ProcessPoolExecutor.

Produces:
  - result/alice_checking/job-plan-001-buy_hold.md
  - result/alice_checking/buy_hold_baseline.csv
  - result/alice_checking/job-result-001-buy_hold.md

Usage:
  cd ~/clawd/workspace/etf
  uv run python alice_checking/job_buy_hold.py
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# project path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from checking.strategy_backtest_lib import compute_metrics, safe_close, strat_buy_hold
from checking.tool_view_verify_hold_etf import get_group_lv2
from core.etf_data_fetcher import ETFDataFetcher
from alice_checking.compare_utils import (
    init_compare_result,
    append_job_section,
)

JOB_ID = "001"
JOB_NAME = "buy_hold"
LOOKBACK_YEARS = 20
OUT_DIR = project_root / "result" / "alice_checking"


# ── worker (module-level for pickle) ─────────────────────────────────────
def _run_one(ticker: str, close_values, close_index, group: str) -> dict | None:
    """Run buy_hold on a single ETF. Called inside ProcessPoolExecutor."""
    close = pd.Series(close_values, index=close_index, name="Close")
    if len(close) < 2:
        return None
    equity = strat_buy_hold(close)
    m = compute_metrics(equity)
    if not m:
        return None
    return {"ticker": ticker, "group": group, **m}


# ── file writers ──────────────────────────────────────────────────────────
def write_plan(start_time: datetime, ticker_count: int) -> Path:
    path = OUT_DIR / f"job-plan-{JOB_ID}-{JOB_NAME}.md"
    path.write_text(
        f"""# Job Plan: {JOB_ID}-{JOB_NAME}
- **Job ID:** {JOB_ID}
- **Started:** {start_time:%Y-%m-%d %H:%M:%S}
- **Status:** RUNNING

## Objective
Run buy_and_hold strategy on all ETFs as the baseline reference.
All subsequent strategy jobs will compare against these results.

## Config
- ETF source: data/etf-v3.yaml ({ticker_count} ETFs)
- Lookback: {LOOKBACK_YEARS} years
- Strategy: strat_buy_hold
- Parallelism: ProcessPoolExecutor (max_workers={os.cpu_count()})

## Expected Output
- result/alice_checking/buy_hold_baseline.csv
- result/alice_checking/job-result-{JOB_ID}-{JOB_NAME}.md
""",
        encoding="utf-8",
    )
    return path


def write_result(
    start_time: datetime,
    end_time: datetime,
    df: pd.DataFrame,
    errors: dict[str, str],
    total_tickers: int,
) -> Path:
    duration = (end_time - start_time).total_seconds()
    ok_count = len(df)
    err_count = len(errors)

    # summary stats
    lines = []
    lines.append(f"# Job Result: {JOB_ID}-{JOB_NAME}")
    lines.append(f"- **Start:** {start_time:%Y-%m-%d %H:%M:%S}")
    lines.append(f"- **End:** {end_time:%Y-%m-%d %H:%M:%S}")
    lines.append(f"- **Duration:** {duration:.0f}s")
    lines.append(f"- **Status:** COMPLETED")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- ETFs processed: {ok_count} / {total_tickers}")
    lines.append(f"- Errors: {err_count}")
    lines.append("")

    if not df.empty:
        lines.append("## Buy & Hold Statistics")
        lines.append("| Metric | Mean | Median | Min | Max |")
        lines.append("|--------|------|--------|-----|-----|")
        for col, label in [
            ("cagr_pct", "CAGR %"),
            ("sharpe", "Sharpe"),
            ("max_drawdown_pct", "Max DD %"),
            ("total_return_pct", "Total Ret %"),
        ]:
            vals = df[col].dropna()
            if vals.empty:
                continue
            lines.append(
                f"| {label} | {vals.mean():.2f} | {vals.median():.2f} "
                f"| {vals.min():.2f} | {vals.max():.2f} |"
            )
        lines.append("")

        # top 5 by CAGR
        top = df.nlargest(5, "cagr_pct")
        lines.append("## Top 5 by CAGR")
        lines.append("| Ticker | Group | CAGR % | Sharpe | Max DD % |")
        lines.append("|--------|-------|--------|--------|----------|")
        for _, r in top.iterrows():
            lines.append(
                f"| {r['ticker']} | {r['group']} | {r['cagr_pct']:.2f} "
                f"| {r['sharpe']:.2f} | {r['max_drawdown_pct']:.2f} |"
            )
        lines.append("")

    if errors:
        lines.append("## Errors")
        for t, msg in errors.items():
            lines.append(f"- {t}: {msg}")
        lines.append("")

    lines.append("## Next")
    lines.append("Scheduled: 002-sma_crossover")

    path = OUT_DIR / f"job-result-{JOB_ID}-{JOB_NAME}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def append_compare_result(df: pd.DataFrame) -> Path:
    """Create compare_result.md with baseline thresholds, scoreboard, and detail section."""
    path = OUT_DIR / "compare_result.md"

    if df.empty:
        return path

    avg_cagr = df["cagr_pct"].mean()
    avg_sharpe = df["sharpe"].mean()
    median_cagr = df["cagr_pct"].median()
    median_sharpe = df["sharpe"].median()
    avg_mdd = df["max_drawdown_pct"].mean()

    # Create file with header + empty scoreboard
    init_compare_result(
        path,
        avg_cagr=avg_cagr,
        avg_sharpe=avg_sharpe,
        median_cagr=median_cagr,
        median_sharpe=median_sharpe,
        avg_mdd=avg_mdd,
        etf_count=len(df),
    )

    # Append baseline detail section
    lines = []
    lines.append(f"## Job {JOB_ID}: {JOB_NAME} (baseline)")
    lines.append(f"_Run: {datetime.now():%Y-%m-%d %H:%M:%S}_\n")
    lines.append(
        "This is the **buy & hold baseline**. "
        "All future jobs compare against these numbers.\n"
    )

    top = df.nlargest(10, "cagr_pct")
    lines.append("### Top 10 ETFs by CAGR")
    lines.append("| Ticker | Group | CAGR % | Sharpe | Max DD % | Total Ret % |")
    lines.append("|--------|-------|--------|--------|----------|-------------|")
    for _, r in top.iterrows():
        lines.append(
            f"| {r['ticker']} | {r['group']} | {r['cagr_pct']:.2f} "
            f"| {r['sharpe']:.2f} | {r['max_drawdown_pct']:.2f} "
            f"| {r['total_return_pct']:.1f} |"
        )
    lines.append("")
    lines.append("---\n")

    append_job_section(path, lines)

    return path


# ── main ──────────────────────────────────────────────────────────────────
def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    start_time = datetime.now()

    # init fetcher
    fetcher = ETFDataFetcher(
        yaml_path=str(project_root / "data" / "etf-v3.yaml"),
        cache_dir=str(project_root / "cache"),
    )
    tickers = list(fetcher.tickers_map.keys())
    print(f"[job_{JOB_NAME}] {len(tickers)} ETFs from etf-v3.yaml")

    # write plan
    write_plan(start_time, len(tickers))
    print(f"[job_{JOB_NAME}] plan written")

    # fetch data
    calendar_days = LOOKBACK_YEARS * 365 + 90
    print(f"[job_{JOB_NAME}] fetching {calendar_days} days of history ...")
    history, fetch_errors = fetcher.fetch_history_days(calendar_days, tickers=tickers)
    print(f"[job_{JOB_NAME}] fetched {len(history)} tickers, {len(fetch_errors)} errors")

    # prepare tasks
    tasks = []
    for ticker, df in history.items():
        close = safe_close(df)
        if close is None:
            fetch_errors[ticker] = "safe_close returned None"
            continue
        info = fetcher.get_ticker_info(ticker)
        group = get_group_lv2(info)
        tasks.append((ticker, close.values, close.index, group))

    # run in parallel
    rows: list[dict] = []
    print(f"[job_{JOB_NAME}] processing {len(tasks)} ETFs with ProcessPoolExecutor ...")
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:
        futures = {
            pool.submit(_run_one, t, cv, ci, g): t for t, cv, ci, g in tasks
        }
        for fut in as_completed(futures):
            ticker = futures[fut]
            try:
                result = fut.result()
                if result:
                    rows.append(result)
                else:
                    fetch_errors[ticker] = "compute_metrics returned empty"
            except Exception as exc:
                fetch_errors[ticker] = str(exc)

    # build dataframe & save csv
    df_all = pd.DataFrame(rows)
    if not df_all.empty:
        for col in ("start_date", "end_date"):
            if col in df_all.columns:
                df_all[col] = pd.to_datetime(df_all[col]).dt.strftime("%Y-%m-%d")
        df_all = df_all.sort_values("cagr_pct", ascending=False).reset_index(drop=True)

    csv_path = OUT_DIR / "buy_hold_baseline.csv"
    df_all.to_csv(csv_path, index=False)
    print(f"[job_{JOB_NAME}] saved {csv_path} ({len(df_all)} rows)")

    # write result
    end_time = datetime.now()
    write_result(start_time, end_time, df_all, fetch_errors, len(tickers))

    # append to shared compare_result.md
    append_compare_result(df_all)
    print(f"[job_{JOB_NAME}] done in {(end_time - start_time).total_seconds():.0f}s")


if __name__ == "__main__":
    main()
