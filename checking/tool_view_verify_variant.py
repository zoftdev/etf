"""tool_view_verify_variant.py

Verify a *single* parameterized variant (from variants grid) vs buy_hold.

Outputs:
- result/variant_verify__<variant_key>.csv (per-ticker metrics for buy_hold + variant)
- result/variant_compare__<variant_key>.csv (one row per ticker: variant metrics + buy_hold baseline + deltas)
- result/variant_verify__<variant_key>.html (simple report)

Usage:
  cd ~/clawd/workspace/etf
  uv run python checking/tool_view_verify_variant.py --years 20 --variant sma_10_100

Notes:
- Uses the same ETF universe and data fetcher as other checking tools.
- This is intentionally lightweight (no heavy plotly dashboard). The grid run is the source
  of truth for rank-search; this tool is for re-running one candidate to sanity-check.
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
from checking.strategy_backtest_lib import compute_metrics, safe_close
from checking.tool_run_variants_grid import build_variants
from checking.tool_view_verify_hold_etf import get_group_lv2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify one variant vs buy_hold")
    p.add_argument("--years", type=int, default=20)
    p.add_argument("--variant", type=str, required=True, help="Variant key (e.g., sma_10_100)")
    p.add_argument("--out_dir", type=str, default="result")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    variants = {v.key: v for v in build_variants()}
    if args.variant not in variants:
        raise SystemExit(f"Unknown variant: {args.variant}. Known={len(variants)}")

    v = variants[args.variant]
    buy = variants["buy_hold"]

    calendar_days = args.years * 365 + max(30, args.years * 3)

    fetcher = ETFDataFetcher()
    tickers = list(fetcher.tickers_map.keys())

    print(f"Fetching {len(tickers)} tickers, {args.years} years (~{calendar_days} calendar days)...")
    history, errors = fetcher.fetch_history_days(calendar_days, tickers=tickers)
    if errors:
        print(f"Errors ({len(errors)}): {list(errors.keys())[:10]}...")

    rows = []
    for ticker, df in history.items():
        close = safe_close(df)
        if close is None:
            continue

        info = fetcher.get_ticker_info(ticker)
        group = get_group_lv2(info)

        # run buy_hold
        eq_b = buy.fn(df, close)
        mb = compute_metrics(eq_b)
        if not mb:
            continue

        # run variant
        eq_v = v.fn(df, close)
        mv = compute_metrics(eq_v)
        if not mv:
            continue

        rows.append(
            {
                "ticker": ticker,
                "group": group,
                "start_date": mv["start_date"],
                "end_date": mv["end_date"],
                "years": mv["years"],
                "variant": v.key,
                "variant_name": v.name,
                **{f"v_{k}": mv[k] for k in ["total_return_pct", "cagr_pct", "max_drawdown_pct", "vol_ann_pct", "sharpe"]},
                **{f"bh_{k}": mb[k] for k in ["total_return_pct", "cagr_pct", "max_drawdown_pct", "vol_ann_pct", "sharpe"]},
            }
        )

    if not rows:
        print("No results")
        return

    out_dir = project_root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(rows)
    df["delta_cagr_pct"] = df["v_cagr_pct"] - df["bh_cagr_pct"]
    df["delta_sharpe"] = df["v_sharpe"] - df["bh_sharpe"]
    df["delta_mdd_pct"] = df["v_max_drawdown_pct"] - df["bh_max_drawdown_pct"]

    # Save CSVs
    base = out_dir / f"variant_compare__{v.key}.csv"
    df2 = df.copy()
    df2["start_date"] = pd.to_datetime(df2["start_date"]).dt.strftime("%Y-%m-%d")
    df2["end_date"] = pd.to_datetime(df2["end_date"]).dt.strftime("%Y-%m-%d")
    df2.to_csv(base, index=False)
    print(f"Saved: {base}")

    # Simple HTML report
    stats = {
        "tickers": int(df["ticker"].nunique()),
        "win_rate_cagr_vs_bh": float((df["delta_cagr_pct"] > 0).mean()),
        "avg_delta_cagr": float(df["delta_cagr_pct"].mean()),
        "median_delta_cagr": float(df["delta_cagr_pct"].median()),
        "avg_delta_sharpe": float(df["delta_sharpe"].mean()),
        "median_delta_sharpe": float(df["delta_sharpe"].median()),
    }

    top = df.sort_values("v_sharpe", ascending=False).head(25)
    bot = df.sort_values("v_sharpe", ascending=True).head(25)

    html = f"""
<!doctype html>
<html>
<head>
<meta charset=\"utf-8\"/>
<title>Variant verify: {v.key}</title>
<style>
body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 20px; }}
code, pre {{ background: #f6f8fa; padding: 2px 6px; border-radius: 6px; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
th, td {{ border: 1px solid #ddd; padding: 6px 8px; font-size: 12px; }}
th {{ background: #fafafa; }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
</style>
</head>
<body>
<h2>Variant verify: <code>{v.key}</code></h2>
<p><b>Name:</b> {v.name}</p>
<p><b>Universe tickers:</b> {stats['tickers']}</p>
<ul>
  <li><b>Win-rate (CAGR &gt; buy_hold):</b> {stats['win_rate_cagr_vs_bh']*100:.1f}%</li>
  <li><b>Avg ΔCAGR:</b> {stats['avg_delta_cagr']:.2f} pp (median {stats['median_delta_cagr']:.2f} pp)</li>
  <li><b>Avg ΔSharpe:</b> {stats['avg_delta_sharpe']:.3f} (median {stats['median_delta_sharpe']:.3f})</li>
</ul>

<h3>Top 25 tickers by variant Sharpe</h3>
{top[['ticker','group','v_sharpe','v_cagr_pct','v_max_drawdown_pct','bh_cagr_pct','bh_max_drawdown_pct','delta_cagr_pct','delta_sharpe']].to_html(index=False, float_format=lambda x: f'{x:0.3f}', classes='')}

<h3>Bottom 25 tickers by variant Sharpe</h3>
{bot[['ticker','group','v_sharpe','v_cagr_pct','v_max_drawdown_pct','bh_cagr_pct','bh_max_drawdown_pct','delta_cagr_pct','delta_sharpe']].to_html(index=False, float_format=lambda x: f'{x:0.3f}', classes='')}

<p>Generated by <code>checking/tool_view_verify_variant.py</code></p>
</body>
</html>
"""

    out_html = out_dir / f"variant_verify__{v.key}.html"
    out_html.write_text(html, encoding="utf-8")
    print(f"Saved: {out_html}")


if __name__ == "__main__":
    main()
