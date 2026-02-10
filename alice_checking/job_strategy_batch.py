"""job_strategy_batch.py -- Jobs 002-013: Run a strategy family's variant grid.

Runs all parameter variants for one strategy family against every ETF,
compares to buy_hold baseline, and reports winners.

Uses variant definitions from checking/tool_run_variants_grid.py.

Usage:
  cd ~/clawd/workspace/etf
  uv run python alice_checking/job_strategy_batch.py --family sma --job-id 002
"""

from __future__ import annotations

import argparse
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

from checking.strategy_backtest_lib import (
    compute_metrics,
    safe_close,
    strat_bollinger_mean_reversion,
    strat_crash_filter_drawdown,
    strat_donchian,
    strat_ema_crossover,
    strat_keltner_breakout,
    strat_macd_crossover,
    strat_momentum,
    strat_rsi_mean_reversion,
    strat_sma_crossover,
    strat_stochrsi_mean_reversion,
    strat_trend_filter,
    strat_vol_targeting,
)
from checking.tool_run_variants_grid import build_variants
from checking.tool_view_verify_hold_etf import get_group_lv2
from core.etf_data_fetcher import ETFDataFetcher
from alice_checking.compare_utils import (
    append_job_section,
    append_winners_to_scoreboard,
)

LOOKBACK_YEARS = 20
OUT_DIR = project_root / "result" / "alice_checking"

# Family name -> variant key prefix (must match keys in build_variants())
FAMILY_PREFIX = {
    "sma": "sma_",
    "ema": "ema_",
    "momentum": "mom_",
    "rsi": "rsi_",
    "bollinger": "boll_",
    "donchian": "donch_",
    "macd": "macd_",
    "keltner": "kelt_",
    "stochrsi": "stochrsi_",
    "vol_target": "vol_",
    "crash_filter": "crash_",
    "trend_filter": "trend_",
}


# ── variant helpers ──────────────────────────────────────────────────────
def _fix_params(family: str, params: dict) -> dict:
    """Fix params from build_variants() to match strategy function signatures.

    build_variants() stores params with keys that don't always match the
    strategy function signatures.  This function remaps/adds defaults.
    """
    p = dict(params)
    if family == "bollinger":
        # build_variants uses "boll_window"; function expects "window"
        p["window"] = p.pop("boll_window")
    elif family == "vol_target":
        p.setdefault("trend_window", 200)
        p.setdefault("max_leverage", 1.0)
        p["target_vol_ann_pct"] = float(p["target_vol_ann_pct"])
    elif family == "crash_filter":
        p.setdefault("sma_window", 200)
        p["dd_threshold_pct"] = float(p["dd_threshold_pct"])
    elif family == "keltner":
        p["atr_mult"] = float(p["atr_mult"])
    elif family == "stochrsi":
        p["entry"] = float(p["entry"])
        p["exit"] = float(p["exit"])
    elif family == "rsi":
        p["entry_rsi"] = float(p["entry_rsi"])
        p["exit_rsi"] = float(p["exit_rsi"])
    return p


def get_family_variants(family: str) -> list[tuple[str, dict]]:
    """Return [(variant_key, fixed_params), ...] for the given family."""
    prefix = FAMILY_PREFIX[family]
    all_variants = build_variants()
    filtered = []
    for v in all_variants:
        if v.key.startswith(prefix):
            fixed = _fix_params(family, v.params)
            filtered.append((v.key, fixed))
    return filtered


# ── strategy dispatch (module-level for ProcessPoolExecutor) ─────────────
def _call_strategy(
    family: str, close: pd.Series, df: pd.DataFrame, params: dict,
) -> pd.Series:
    """Dispatch to the correct strategy function based on family."""
    if family == "sma":
        return strat_sma_crossover(close, **params)
    elif family == "ema":
        return strat_ema_crossover(close, **params)
    elif family == "momentum":
        return strat_momentum(close, **params)
    elif family == "rsi":
        return strat_rsi_mean_reversion(close, **params)
    elif family == "bollinger":
        return strat_bollinger_mean_reversion(close, **params)
    elif family == "donchian":
        return strat_donchian(close, **params)
    elif family == "macd":
        return strat_macd_crossover(close, **params)
    elif family == "keltner":
        return strat_keltner_breakout(df, **params)
    elif family == "stochrsi":
        return strat_stochrsi_mean_reversion(close, **params)
    elif family == "vol_target":
        return strat_vol_targeting(close, **params)
    elif family == "crash_filter":
        return strat_crash_filter_drawdown(close, **params)
    elif family == "trend_filter":
        return strat_trend_filter(close, **params)
    else:
        raise ValueError(f"Unknown family: {family}")


# ── worker (module-level for pickle) ─────────────────────────────────────
def _run_etf(
    ticker,
    close_values,
    close_index,
    df_values,
    df_columns,
    df_index,
    group,
    family,
    variants_config,
) -> list[dict]:
    """Run all variants in the family for one ETF.  Called in ProcessPoolExecutor."""
    close = pd.Series(close_values, index=close_index, name="Close")
    df = pd.DataFrame(df_values, index=df_index, columns=df_columns)

    results = []
    for v_key, params in variants_config:
        try:
            equity = _call_strategy(family, close, df, params)
            m = compute_metrics(equity)
            if m:
                results.append({"ticker": ticker, "group": group, "variant": v_key, **m})
        except Exception:
            pass
    return results


# ── file writers ─────────────────────────────────────────────────────────
def write_plan(
    job_id: str, family: str, start_time: datetime,
    ticker_count: int, variant_count: int,
) -> Path:
    path = OUT_DIR / f"job-plan-{job_id}-{family}.md"
    path.write_text(
        f"""# Job Plan: {job_id}-{family}
- **Job ID:** {job_id}
- **Started:** {start_time:%Y-%m-%d %H:%M:%S}
- **Status:** RUNNING

## Objective
Run all {family} strategy variants against all ETFs and compare to buy_hold baseline.

## Config
- Family: {family}
- Variants: {variant_count}
- ETFs: {ticker_count}
- Lookback: {LOOKBACK_YEARS} years
- Parallelism: ProcessPoolExecutor (max_workers={os.cpu_count()})
""",
        encoding="utf-8",
    )
    return path


def write_result(
    job_id: str,
    family: str,
    start_time: datetime,
    end_time: datetime,
    df_all: pd.DataFrame,
    baseline: dict,
    errors: dict,
    total_tickers: int,
    variant_count: int,
    winners_list: list[dict],
) -> Path:
    duration = (end_time - start_time).total_seconds()
    lines = []
    lines.append(f"# Job Result: {job_id}-{family}")
    lines.append(f"- **Start:** {start_time:%Y-%m-%d %H:%M:%S}")
    lines.append(f"- **End:** {end_time:%Y-%m-%d %H:%M:%S}")
    lines.append(f"- **Duration:** {duration:.0f}s")
    lines.append("- **Status:** COMPLETED")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Family: {family}")
    lines.append(f"- Variants tested: {variant_count}")
    lines.append(f"- ETFs: {total_tickers}")
    lines.append(f"- Total backtests: {len(df_all)}")
    lines.append(f"- Errors: {len(errors)}")
    lines.append(
        f"- Baseline: avg_cagr={baseline['avg_cagr']:.2f}%, "
        f"avg_sharpe={baseline['avg_sharpe']:.2f}"
    )
    lines.append("")

    lines.append(f"## Winners ({len(winners_list)} / {variant_count} variants beat baseline)")
    if winners_list:
        sorted_w = sorted(winners_list, key=lambda w: w["avg_cagr"], reverse=True)
        lines.append("| Variant | Avg CAGR | Avg Sharpe | Avg MDD | Beat CAGR | Beat Sharpe |")
        lines.append("|---------|----------|------------|---------|-----------|-------------|")
        for w in sorted_w:
            bc = "Y" if w["beat_cagr"] else "-"
            bs = "Y" if w["beat_sharpe"] else "-"
            lines.append(
                f"| {w['variant']} | {w['avg_cagr']:.2f} | {w['avg_sharpe']:.2f} "
                f"| {w['avg_mdd']:.2f} | {bc} | {bs} |"
            )
        lines.append("")
    else:
        lines.append("_No variants beat the baseline._\n")

    if errors:
        lines.append("## Errors")
        for t, msg in list(errors.items())[:20]:
            lines.append(f"- {t}: {msg}")
        lines.append("")

    path = OUT_DIR / f"job-result-{job_id}-{family}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def update_compare_result(
    job_id: str,
    family: str,
    end_time: datetime,
    variant_count: int,
    winners_list: list[dict],
) -> None:
    """Insert winners into scoreboard and append a per-job detail section."""
    compare_path = OUT_DIR / "compare_result.md"

    # Insert winners into scoreboard
    if winners_list:
        append_winners_to_scoreboard(compare_path, winners_list)

    # Append per-job section
    section = []
    section.append(f"## Job {job_id}: {family}")
    section.append(f"_Run: {end_time:%Y-%m-%d %H:%M:%S}_\n")
    section.append(
        f"Variants tested: {variant_count} | Winners: {len(winners_list)}\n"
    )

    if winners_list:
        sorted_w = sorted(winners_list, key=lambda w: w["avg_cagr"], reverse=True)
        section.append("### Winners")
        section.append("| Variant | Avg CAGR | Avg Sharpe | Avg MDD |")
        section.append("|---------|----------|------------|---------|")
        for w in sorted_w:
            section.append(
                f"| {w['variant']} | {w['avg_cagr']:.2f} "
                f"| {w['avg_sharpe']:.2f} | {w['avg_mdd']:.2f} |"
            )
        section.append("")
    else:
        section.append("_No variants beat the baseline._\n")

    section.append("---\n")
    append_job_section(compare_path, section)


# ── main ─────────────────────────────────────────────────────────────────
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run strategy family variant grid")
    p.add_argument(
        "--family",
        required=True,
        choices=sorted(FAMILY_PREFIX.keys()),
        help="Strategy family to run",
    )
    p.add_argument("--job-id", required=True, help="Job ID (e.g. 002)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    job_id = args.job_id
    family = args.family

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    start_time = datetime.now()

    # Get variants for this family
    variants_config = get_family_variants(family)
    print(f"[job_{family}] {len(variants_config)} variants for family '{family}'")

    if not variants_config:
        print(f"[job_{family}] ERROR: no variants found for family '{family}'")
        return

    # Load baseline thresholds from buy_hold
    baseline_csv = OUT_DIR / "buy_hold_baseline.csv"
    bl = pd.read_csv(baseline_csv)
    baseline = {
        "avg_cagr": bl["cagr_pct"].mean(),
        "avg_sharpe": bl["sharpe"].mean(),
    }
    print(
        f"[job_{family}] baseline: avg_cagr={baseline['avg_cagr']:.2f}%, "
        f"avg_sharpe={baseline['avg_sharpe']:.2f}"
    )

    # Init fetcher
    fetcher = ETFDataFetcher(
        yaml_path=str(project_root / "data" / "etf-v3.yaml"),
        cache_dir=str(project_root / "cache"),
    )
    tickers = list(fetcher.tickers_map.keys())
    print(f"[job_{family}] {len(tickers)} ETFs from etf-v3.yaml")

    # Write plan
    write_plan(job_id, family, start_time, len(tickers), len(variants_config))

    # Fetch data
    calendar_days = LOOKBACK_YEARS * 365 + 90
    print(f"[job_{family}] fetching {calendar_days} days of history ...")
    history, fetch_errors = fetcher.fetch_history_days(calendar_days, tickers=tickers)
    print(f"[job_{family}] fetched {len(history)} tickers, {len(fetch_errors)} errors")

    # Prepare tasks -- one per ETF
    tasks = []
    for ticker, df in history.items():
        close = safe_close(df)
        if close is None:
            fetch_errors[ticker] = "safe_close returned None"
            continue
        info = fetcher.get_ticker_info(ticker)
        group = get_group_lv2(info)

        # For keltner, pass OHLC columns; for others, Close-only DataFrame
        if family == "keltner":
            ohlc_cols = [c for c in ["Open", "High", "Low", "Close"] if c in df.columns]
            df_subset = df[ohlc_cols].loc[close.index]
        else:
            df_subset = close.to_frame(name="Close")

        tasks.append((
            ticker,
            close.values,
            close.index,
            df_subset.values,
            df_subset.columns.tolist(),
            df_subset.index,
            group,
            family,
            variants_config,
        ))

    # Run in parallel (one ETF per worker, all variants inside)
    all_rows: list[dict] = []
    errors = dict(fetch_errors)
    n_backtests = len(tasks) * len(variants_config)
    print(
        f"[job_{family}] running {len(tasks)} ETFs x {len(variants_config)} variants "
        f"= {n_backtests} backtests ..."
    )
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:
        futures = {pool.submit(_run_etf, *t): t[0] for t in tasks}
        for fut in as_completed(futures):
            ticker = futures[fut]
            try:
                results = fut.result()
                all_rows.extend(results)
            except Exception as exc:
                errors[ticker] = str(exc)

    # Build result DataFrame
    df_all = pd.DataFrame(all_rows)
    if not df_all.empty:
        for col in ("start_date", "end_date"):
            if col in df_all.columns:
                df_all[col] = pd.to_datetime(df_all[col]).dt.strftime("%Y-%m-%d")

    # Save detailed CSV
    csv_path = OUT_DIR / f"{family}_results.csv"
    df_all.to_csv(csv_path, index=False)
    print(f"[job_{family}] saved {csv_path} ({len(df_all)} rows)")

    # Compute per-variant averages and find winners
    winners_list: list[dict] = []
    if not df_all.empty:
        var_avg = (
            df_all.groupby("variant")
            .agg(
                avg_cagr=("cagr_pct", "mean"),
                avg_sharpe=("sharpe", "mean"),
                avg_mdd=("max_drawdown_pct", "mean"),
            )
            .reset_index()
        )

        for _, row in var_avg.iterrows():
            beat_cagr = row["avg_cagr"] > baseline["avg_cagr"]
            beat_sharpe = row["avg_sharpe"] > baseline["avg_sharpe"]
            if beat_cagr or beat_sharpe:
                winners_list.append({
                    "variant": row["variant"],
                    "family": family,
                    "avg_cagr": row["avg_cagr"],
                    "avg_sharpe": row["avg_sharpe"],
                    "avg_mdd": row["avg_mdd"],
                    "beat_cagr": beat_cagr,
                    "beat_sharpe": beat_sharpe,
                    "job": job_id,
                })

    # Write result file
    end_time = datetime.now()
    write_result(
        job_id, family, start_time, end_time, df_all,
        baseline, errors, len(tickers), len(variants_config), winners_list,
    )

    # Update compare_result.md (scoreboard + job section)
    update_compare_result(job_id, family, end_time, len(variants_config), winners_list)

    duration = (end_time - start_time).total_seconds()
    print(f"[job_{family}] done in {duration:.0f}s -- {len(winners_list)} winners")


if __name__ == "__main__":
    main()
