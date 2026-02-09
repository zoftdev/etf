"""tool_run_variants_grid.py

Run parameter variants (grid) for multiple strategies and save a combined CSV.

This is meant for long unattended research runs.

Output:
- result/variants_grid.csv (ETF × variant)

Usage:
  cd ~/clawd/workspace/etf
  uv run python checking/tool_run_variants_grid.py --years 20

Notes:
- Uses Close only.
- No fees/slippage yet.
- Strategy variants are defined in-code (small, curated grids to keep runtime reasonable).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path

# project path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd

from core.etf_data_fetcher import ETFDataFetcher
from checking.strategy_backtest_lib import (
    compute_metrics,
    safe_close,
    strat_buy_hold,
    strat_ema_crossover,
    strat_momentum,
    strat_rsi_mean_reversion,
    strat_sma_crossover,
)
from checking.tool_view_verify_hold_etf import get_group_lv2


@dataclass(frozen=True)
class Variant:
    key: str
    name: str
    fn: callable
    params: dict


def build_variants() -> list[Variant]:
    variants: list[Variant] = []

    # Baseline
    variants.append(Variant("buy_hold", "Buy & Hold", lambda close: strat_buy_hold(close), {}))

    # SMA crossover grid (small)
    for fast, slow in [(20, 200), (50, 200), (50, 150)]:
        k = f"sma_{fast}_{slow}"
        variants.append(
            Variant(k, f"SMA Crossover ({fast}/{slow})", lambda close, f=fast, s=slow: strat_sma_crossover(close, fast=f, slow=s), {"fast": fast, "slow": slow})
        )

    # EMA crossover grid (small + optional band)
    for fast, slow, band in [(10, 200, 0.0), (20, 200, 0.0), (20, 200, 0.5), (50, 200, 0.0)]:
        k = f"ema_{fast}_{slow}_band{str(band).replace('.', 'p')}"
        variants.append(
            Variant(
                k,
                f"EMA Crossover ({fast}/{slow}) band={band}%",
                lambda close, f=fast, s=slow, b=band: strat_ema_crossover(close, fast=f, slow=s, band_pct=b),
                {"fast": fast, "slow": slow, "band_pct": band},
            )
        )

    # Momentum grid
    for lookback, skip in [(63, 5), (126, 21), (252, 21), (252, 0)]:
        k = f"mom_{lookback}_skip{skip}"
        variants.append(
            Variant(
                k,
                f"Momentum ({lookback}d skip {skip}d)",
                lambda close, lb=lookback, sk=skip: strat_momentum(close, lookback_days=lb, skip_recent_days=sk, threshold_pct=0.0),
                {"lookback_days": lookback, "skip_recent_days": skip, "threshold_pct": 0.0},
            )
        )

    # RSI mean reversion grid
    for w, entry, exit_ in [(7, 25, 50), (14, 30, 50), (14, 25, 55), (21, 30, 55)]:
        k = f"rsi_{w}_{entry}_{exit_}"
        variants.append(
            Variant(
                k,
                f"RSI MR (w={w}, entry<{entry}, exit>{exit_})",
                lambda close, ww=w, en=entry, ex=exit_: strat_rsi_mean_reversion(close, rsi_window=ww, entry_rsi=float(en), exit_rsi=float(ex)),
                {"rsi_window": w, "entry_rsi": entry, "exit_rsi": exit_},
            )
        )

    return variants


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run a curated grid of strategy variants")
    p.add_argument("--years", type=int, default=20)
    p.add_argument("--out", type=str, default="variants_grid")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    variants = build_variants()
    calendar_days = args.years * 365 + max(30, args.years * 3)

    fetcher = ETFDataFetcher()
    tickers = list(fetcher.tickers_map.keys())
    print(f"Fetching {len(tickers)} tickers, {args.years} years (~{calendar_days} calendar days)...")
    history, errors = fetcher.fetch_history_days(calendar_days, tickers=tickers)
    if errors:
        print(f"Errors ({len(errors)}): {list(errors.keys())[:10]}...")

    rows: list[dict] = []

    for ticker, df in history.items():
        close = safe_close(df)
        if close is None:
            continue

        info = fetcher.get_ticker_info(ticker)
        group = get_group_lv2(info)

        for v in variants:
            try:
                equity = v.fn(close)
                m = compute_metrics(equity)
            except Exception as e:
                print(f"Variant {v.key} failed for {ticker}: {e}")
                continue

            if not m:
                continue

            rows.append(
                {
                    "ticker": ticker,
                    "group": group,
                    "variant": v.key,
                    "variant_name": v.name,
                    **v.params,
                    **m,
                }
            )

    if not rows:
        print("No results")
        return

    df_all = pd.DataFrame(rows)

    out_dir = Path(__file__).resolve().parent.parent / "result"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / f"{args.out}.csv"

    # format dates
    df_out = df_all.copy()
    df_out["start_date"] = df_out["start_date"].dt.strftime("%Y-%m-%d")
    df_out["end_date"] = df_out["end_date"].dt.strftime("%Y-%m-%d")

    df_out.to_csv(out_csv, index=False)
    print(f"Saved: {out_csv}")


if __name__ == "__main__":
    main()
