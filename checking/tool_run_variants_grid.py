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
- Strategy variants are defined in-code.
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
    strat_bollinger_mean_reversion,
    strat_donchian,
    strat_vol_targeting,
    strat_trend_filter,
    strat_crash_filter_drawdown,
    strat_macd_crossover,
    strat_keltner_breakout,
    strat_stochrsi_mean_reversion,
)
from checking.tool_view_verify_hold_etf import get_group_lv2


@dataclass(frozen=True)
class Variant:
    key: str
    name: str
    fn: callable  # (df, close) -> equity
    params: dict


def build_variants() -> list[Variant]:
    """Build *all* variants we want to test overnight.

    Keep this as the single source of truth for what "all variants" means.
    """
    variants: list[Variant] = []

    # Baseline
    variants.append(Variant("buy_hold", "Buy & Hold", lambda df, close: strat_buy_hold(close), {}))

    # 2) SMA Crossover
    sma_fast = [10, 20, 50, 100]
    sma_slow = [100, 150, 200, 250]
    for fast, slow in product(sma_fast, sma_slow):
        if fast >= slow:
            continue
        k = f"sma_{fast}_{slow}"
        variants.append(
            Variant(k, f"SMA Crossover ({fast}/{slow})", lambda df, close, f=fast, s=slow: strat_sma_crossover(close, fast=f, slow=s), {"fast": fast, "slow": slow})
        )

    # 3) EMA Crossover
    ema_fast = [10, 20, 50]
    ema_slow = [100, 150, 200]
    ema_band = [0.0, 0.25, 0.5]
    for fast, slow, band in product(ema_fast, ema_slow, ema_band):
        if fast >= slow:
            continue
        k = f"ema_{fast}_{slow}_band{str(band).replace('.', 'p')}"
        variants.append(
            Variant(
                k,
                f"EMA Crossover ({fast}/{slow}) band={band}%",
                lambda df, close, f=fast, s=slow, b=band: strat_ema_crossover(close, fast=f, slow=s, band_pct=b),
                {"fast": fast, "slow": slow, "band_pct": band},
            )
        )

    # 4) Donchian breakout
    for entry_window, exit_window in product([20, 55, 100], [10, 20, 55]):
        k = f"donch_{entry_window}_{exit_window}"
        variants.append(
            Variant(
                k,
                f"Donchian Breakout ({entry_window}/{exit_window})",
                lambda df, close, en=entry_window, ex=exit_window: strat_donchian(close, entry_window=en, exit_window=ex),
                {"entry_window": entry_window, "exit_window": exit_window},
            )
        )

    # 5) Bollinger mean reversion
    for window, num_std, exit_rule, max_hold in product([20, 50], [1.5, 2.0, 2.5], ["mid", "upper"], [None, 20, 60]):
        k = f"boll_{window}_{str(num_std).replace('.', 'p')}_{exit_rule}_mh{max_hold if max_hold is not None else 'N'}"
        variants.append(
            Variant(
                k,
                f"Boll MR (w={window}, sd={num_std}, exit={exit_rule}, max_hold={max_hold})",
                lambda df, close, w=window, sd=num_std, er=exit_rule, mh=max_hold: strat_bollinger_mean_reversion(close, window=w, num_std=sd, exit_rule=er, max_hold_days=mh),
                {"boll_window": window, "num_std": num_std, "exit_rule": exit_rule, "max_hold_days": max_hold},
            )
        )

    # 6) RSI mean reversion
    for w, entry, exit_, max_hold in product([7, 14, 21], [20, 25, 30], [45, 50, 55], [None, 10, 30]):
        k = f"rsi_{w}_{entry}_{exit_}_mh{max_hold if max_hold is not None else 'N'}"
        variants.append(
            Variant(
                k,
                f"RSI MR (w={w}, entry<{entry}, exit>{exit_}, max_hold={max_hold})",
                lambda df, close, ww=w, en=entry, ex=exit_, mh=max_hold: strat_rsi_mean_reversion(close, rsi_window=ww, entry_rsi=float(en), exit_rsi=float(ex), max_hold_days=mh),
                {"rsi_window": w, "entry_rsi": entry, "exit_rsi": exit_, "max_hold_days": max_hold},
            )
        )

    # 7) Momentum
    for lookback, skip, thresh in product([63, 126, 252], [0, 5, 21], [0.0, 1.0, 2.0]):
        k = f"mom_{lookback}_skip{skip}_th{str(thresh).replace('.', 'p')}"
        variants.append(
            Variant(
                k,
                f"Momentum ({lookback}d skip {skip}d thr={thresh}%)",
                lambda df, close, lb=lookback, sk=skip, th=thresh: strat_momentum(close, lookback_days=lb, skip_recent_days=sk, threshold_pct=th),
                {"lookback_days": lookback, "skip_recent_days": skip, "threshold_pct": thresh},
            )
        )

    # 8) Vol targeting
    for vol_lb, tgt, tf in product([20, 63, 126], [8, 10, 12, 15], ["none", "sma_200"]):
        k = f"vol_{vol_lb}_t{tgt}_{tf}"
        variants.append(
            Variant(
                k,
                f"VolTarget (lb={vol_lb}, tgt={tgt}%, tf={tf})",
                lambda df, close, vlb=vol_lb, t=tgt, tf_=tf: strat_vol_targeting(close, vol_lookback_days=vlb, target_vol_ann_pct=float(t), trend_filter=tf_, trend_window=200, max_leverage=1.0),
                {"vol_lookback_days": vol_lb, "target_vol_ann_pct": tgt, "trend_filter": tf},
            )
        )

    # 9) Trend filter + DCA (proxy)
    # NOTE: true DCA needs cashflow + XIRR; for now we model the *trend filter* only.
    for tw in [150, 200, 250]:
        k = f"trend_sma{tw}"
        variants.append(
            Variant(
                k,
                f"Trend filter (close>=SMA{tw}) [DCA proxy]",
                lambda df, close, w=tw: strat_trend_filter(close, trend_window=w),
                {"trend_window": tw},
            )
        )

    # 10) Crash filter (drawdown)
    for dd_lb, dd_th, reentry in product([63, 126, 252], [-10, -15, -20], ["new_high", "sma_200", "cooldown"]):
        if reentry == "cooldown":
            cooldowns = [10, 20, 60]
        else:
            cooldowns = [20]
        for cd in cooldowns:
            k = f"crash_dd{dd_lb}_th{abs(dd_th)}_{reentry}_cd{cd}"
            variants.append(
                Variant(
                    k,
                    f"Crash(dd_lb={dd_lb}, th={dd_th}%, reentry={reentry}, cd={cd})",
                    lambda df, close, lb=dd_lb, th=dd_th, rr=reentry, cd_=cd: strat_crash_filter_drawdown(
                        close, dd_lookback_days=lb, dd_threshold_pct=float(th), reentry_rule=rr, cooldown_days=cd_, sma_window=200
                    ),
                    {"dd_lookback_days": dd_lb, "dd_threshold_pct": dd_th, "reentry_rule": reentry, "cooldown_days": cd},
                )
            )

    # 11) MACD signal-line crossover
    for fast, slow, sig, zf in product([8, 12, 16], [20, 26, 35], [5, 9, 12], [0, 1]):
        if fast >= slow:
            continue
        k = f"macd_{fast}_{slow}_{sig}_zf{zf}"
        variants.append(
            Variant(
                k,
                f"MACD ({fast}/{slow}/{sig}) zero_filter={bool(zf)}",
                lambda df, close, f=fast, s=slow, si=sig, z=zf: strat_macd_crossover(close, fast_span=f, slow_span=s, signal_span=si, use_zero_filter=bool(z)),
                {"fast_span": fast, "slow_span": slow, "signal_span": sig, "use_zero_filter": bool(zf)},
            )
        )

    # 12) Keltner channel breakout (uses OHLC when present)
    for ema_w, atr_w, mult, exit_rule in product([20, 50], [10, 20], [1.5, 2.0, 2.5], ["mid", "lower"]):
        mult_key = str(mult).replace(".", "p")
        k = f"kelt_{ema_w}_{atr_w}_m{mult_key}_x{exit_rule}"
        variants.append(
            Variant(
                k,
                f"Keltner BO (ema={ema_w}, atr={atr_w}, mult={mult}, exit={exit_rule})",
                lambda df, close, ew=ema_w, aw=atr_w, m=mult, xr=exit_rule: strat_keltner_breakout(df, ema_window=ew, atr_window=aw, atr_mult=float(m), exit_rule=xr),
                {"ema_window": ema_w, "atr_window": atr_w, "atr_mult": mult, "exit_rule": exit_rule},
            )
        )

    # 13) StochRSI mean reversion
    for rsi_w, stoch_w, k_sm, d_sm, entry, exit_, mh in product([14], [14, 21], [1, 3], [1, 3], [0.1, 0.2], [0.8, 0.9], [None, 10, 30]):
        mh_key = mh if mh is not None else "N"
        k_entry = str(entry).replace(".", "p")
        k_exit = str(exit_).replace(".", "p")
        k = f"stochrsi_r{rsi_w}_s{stoch_w}_k{k_sm}_d{d_sm}_e{k_entry}_x{k_exit}_mh{mh_key}"
        variants.append(
            Variant(
                k,
                f"StochRSI MR (rsi={rsi_w}, stoch={stoch_w}, k={k_sm}, d={d_sm}, entry<{entry}, exit>{exit_}, mh={mh})",
                lambda df, close, rw=rsi_w, sw=stoch_w, kk=k_sm, dd=d_sm, en=entry, ex=exit_, mh_=mh: strat_stochrsi_mean_reversion(
                    close,
                    rsi_window=rw,
                    stoch_window=sw,
                    smooth_k=kk,
                    smooth_d=dd,
                    entry=float(en),
                    exit=float(ex),
                    max_hold_days=mh_,
                ),
                {
                    "rsi_window": rsi_w,
                    "stoch_window": stoch_w,
                    "smooth_k": k_sm,
                    "smooth_d": d_sm,
                    "entry": entry,
                    "exit": exit_,
                    "max_hold_days": mh,
                },
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
                equity = v.fn(df, close)
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
