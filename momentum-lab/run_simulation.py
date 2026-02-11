#!/usr/bin/env python3
"""
QuantPedia ETF Momentum Strategy - Main entry point

Orchestrates: simulate → save CSVs → gen_graph

Usage:
  uv run python momentum-lab/run_simulation.py [--spread 0.15] [--show-trades] [--no-graph]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

# Add momentum-lab to path for local imports
_lab_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_lab_dir))

from simulate import ETF_GROUP_NAME, OUT_DIR, SPREAD_PCT, run_simulation
from gen_graph import build_chart


def main() -> None:
    parser = argparse.ArgumentParser(description="QuantPedia ETF Momentum Strategy")
    parser.add_argument("--spread", type=float, default=SPREAD_PCT,
                        help="Transaction cost %% per rebalance")
    parser.add_argument("--show-trades", action="store_true",
                        help="Output merged buy/sell summary")
    parser.add_argument("--no-graph", action="store_true",
                        help="Skip chart generation")
    args = parser.parse_args()

    result_dir = OUT_DIR / ETF_GROUP_NAME
    result_dir.mkdir(parents=True, exist_ok=True)

    print("Fetching 13 ETFs from Yahoo Finance...")
    result = run_simulation(spread=args.spread, show_trades=args.show_trades)

    print(f"Data range: {result.prices.index[0].date()} to {result.prices.index[-1].date()} "
          f"({len(result.prices)} days)")

    m_mom_0 = result.metrics["mom_0"]
    m_mom_015 = result.metrics["mom_015"]
    m_bh = result.metrics["bh"]

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"\nMomentum (spread=0%):")
    print(f"  CAGR:       {m_mom_0.get('cagr_pct', 0):.2f}%")
    print(f"  Sharpe:     {m_mom_0.get('sharpe', 0):.2f}")
    print(f"  Max DD:     {m_mom_0.get('max_drawdown_pct', 0):.2f}%")
    print(f"\nMomentum (spread={args.spread}%):")
    print(f"  CAGR:       {m_mom_015.get('cagr_pct', 0):.2f}%")
    print(f"  Sharpe:     {m_mom_015.get('sharpe', 0):.2f}")
    print(f"  Max DD:     {m_mom_015.get('max_drawdown_pct', 0):.2f}%")
    print(f"\nBuy-Hold (Equal Weight 13 ETFs):")
    print(f"  CAGR:       {m_bh.get('cagr_pct', 0):.2f}%")
    print(f"  Sharpe:     {m_bh.get('sharpe', 0):.2f}")
    print(f"  Max DD:     {m_bh.get('max_drawdown_pct', 0):.2f}%")

    # Save CSVs in result/ETF_GROUP_NAME/
    out_csv = result_dir / "equity_curves.csv"
    result.out_df.to_csv(out_csv)
    print(f"\nSaved {out_csv}")

    metrics_df = pd.DataFrame([
        {"strategy": "momentum_spread0", **m_mom_0},
        {"strategy": result.spread_label, **m_mom_015},
        {"strategy": "buy_hold", **m_bh},
    ])
    metrics_csv = result_dir / "metrics.csv"
    metrics_df.to_csv(metrics_csv, index=False)
    print(f"Saved {metrics_csv}")

    trades_df = pd.DataFrame(result.trades_log)
    if not trades_df.empty:
        trades_df["date"] = pd.to_datetime(trades_df["date"]).dt.strftime("%Y-%m-%d")
    trades_csv = result_dir / "buysell_log.csv"
    trades_df.to_csv(trades_csv, index=False)
    print(f"Saved {trades_csv} ({len(trades_df)} rows)")

    if result.trade_log:
        trade_df = pd.DataFrame(result.trade_log)
        trade_df["date"] = pd.to_datetime(trade_df["date"]).dt.strftime("%Y-%m-%d")
        trade_csv = result_dir / "trade_log.csv"
        trade_df.to_csv(trade_csv, index=False)
        print(f"Saved {trade_csv} ({len(trade_df)} rows)")

    if args.show_trades and result.trades_summary:
        summary_df = pd.DataFrame(result.trades_summary)
        summary_df["date"] = pd.to_datetime(summary_df["date"]).dt.strftime("%Y-%m-%d")
        summary_csv = result_dir / "trades_summary.csv"
        summary_df.to_csv(summary_csv, index=False)
        print(f"Saved {summary_csv}")
        print("\n--- Trades Summary (last 10) ---")
        for row in result.trades_summary[-10:]:
            d = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
            print(f"  {d} | buy: {row['buy']} | sell: {row['sell']} | PnL: {row['sell_pnl_pct']}")

    # Graph
    if not args.no_graph:
        try:
            path = build_chart(
                result.out_df,
                result.holdings_history,
                result.prices,
                first_valid=result.first_valid,
                spread=result.spread,
                spread_label=result.spread_label,
                out_path=result_dir / "momentum_vs_buyhold.html",
            )
            print(f"Saved {path}")
        except ImportError:
            print("Plotly not installed; skip HTML.")


if __name__ == "__main__":
    main()
