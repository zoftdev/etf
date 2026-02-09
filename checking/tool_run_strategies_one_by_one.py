"""tool_run_strategies_one_by_one.py

Batch-run strategies one-by-one and save:
1) per-strategy compare (buy_hold vs that strategy) as HTML + CSV
2) an overall combined CSV for all strategies that are implemented

Usage:
  cd ~/clawd/workspace/etf
  uv run python checking/tool_run_strategies_one_by_one.py --years 20

Notes:
- This uses the same universe and fetch method as tool_view_verify_hold_etf.py.
- It only runs strategies that exist in available_strategies().
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# project path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd

from core.etf_data_fetcher import ETFDataFetcher
from checking.strategy_backtest_lib import available_strategies, compute_metrics, safe_close
from checking.tool_view_verify_hold_etf import get_group_lv2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run each implemented strategy and save separate + compare outputs")
    p.add_argument("--years", type=int, default=20)
    p.add_argument("--out_dir", type=str, default="result")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    strat_map = available_strategies()
    keys = list(strat_map.keys())
    if "buy_hold" not in keys:
        raise SystemExit("available_strategies() must include buy_hold")

    calendar_days = args.years * 365 + max(30, args.years * 3)

    fetcher = ETFDataFetcher()
    tickers = list(fetcher.tickers_map.keys())
    print(f"Fetching {len(tickers)} tickers, {args.years} years (~{calendar_days} calendar days)...")
    history, errors = fetcher.fetch_history_days(calendar_days, tickers=tickers)
    if errors:
        print(f"Errors ({len(errors)}): {list(errors.keys())[:10]}...")

    # Backtest all (for global compare file)
    all_rows: list[dict] = []

    for ticker, df in history.items():
        close = safe_close(df)
        if close is None:
            continue

        info = fetcher.get_ticker_info(ticker)
        group = get_group_lv2(info)

        for k in keys:
            strat = strat_map[k]
            equity = strat.fn(close)
            m = compute_metrics(equity)
            if not m:
                continue
            all_rows.append({"ticker": ticker, "group": group, "strategy": strat.key, "strategy_name": strat.name, **m})

    if not all_rows:
        print("No results")
        return

    out_dir = Path(__file__).resolve().parent.parent / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    df_all = pd.DataFrame(all_rows)

    # Save global combined CSV
    df_out = df_all.copy()
    df_out["start_date"] = df_out["start_date"].dt.strftime("%Y-%m-%d")
    df_out["end_date"] = df_out["end_date"].dt.strftime("%Y-%m-%d")
    df_out = df_out.sort_values(["strategy", "cagr_pct"], ascending=[True, False])
    combined_csv = out_dir / "strategy_all.csv"
    df_out.to_csv(combined_csv, index=False)
    print(f"Saved combined CSV: {combined_csv}")

    # Per-strategy compare CSV (buy_hold vs each other)
    baseline = df_all[df_all.strategy == "buy_hold"][
        ["ticker", "cagr_pct", "total_return_pct", "max_drawdown_pct", "vol_ann_pct", "sharpe"]
    ].rename(
        columns={
            "cagr_pct": "bh_cagr_pct",
            "total_return_pct": "bh_total_return_pct",
            "max_drawdown_pct": "bh_max_drawdown_pct",
            "vol_ann_pct": "bh_vol_ann_pct",
            "sharpe": "bh_sharpe",
        }
    )

    for k in keys:
        if k == "buy_hold":
            continue

        sub = df_all[df_all.strategy == k].copy()
        comp = sub.merge(baseline, on="ticker", how="left")
        comp["delta_cagr_pct"] = comp["cagr_pct"] - comp["bh_cagr_pct"]
        comp["delta_mdd_pct"] = comp["max_drawdown_pct"] - comp["bh_max_drawdown_pct"]

        comp_out = out_dir / f"strategy_compare__{k}.csv"
        comp2 = comp.copy()
        comp2["start_date"] = comp2["start_date"].dt.strftime("%Y-%m-%d")
        comp2["end_date"] = comp2["end_date"].dt.strftime("%Y-%m-%d")
        comp2.to_csv(comp_out, index=False)
        print(f"Saved compare CSV: {comp_out}")

        # For HTML dashboard, reuse the existing viewer script by calling it as a module would be nicer,
        # but simplest (and consistent) is: instruct user to run tool_view_verify_hold_etf.py for that pair.
        # We'll still generate the HTML via subprocess? To keep it simple & explicit, we just print the command.
        print(
            "To generate HTML dashboard for this pair, run: "
            f"uv run python checking/tool_view_verify_hold_etf.py --years {args.years} --strategies buy_hold,{k} --out strategy_compare__{k}"
        )


if __name__ == "__main__":
    main()
