"""Run fine-grain momentum grid and save results + equity curves for top5 vs buy_hold.

Momentum variants from alice_checking grid: lookback 63/126/252, skip 0/5/21, threshold 0/1/2.
Winners: mom_63_skip5_th0p0, mom_63_skip5_th1p0.

Fine-grain around winners: lookback 55–75, skip 3–7, threshold 0–1.0.

Usage:
  cd ~/clawd/workspace/etf
  uv run python momentum-test/run_fine_grid.py

Outputs:
  momentum-test/out/momentum_fine_results.csv   — per (ticker, variant) metrics
  momentum-test/out/equity_curves.csv           — date, ticker, strategy, equity (for top5 + buy_hold)
  momentum-test/out/top5_variants.json          — top 5 variant keys by avg CAGR
  momentum-test/out/momentum_vs_buyhold.html    — interactive Plotly chart
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

# project root = workspace/etf
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from checking.strategy_backtest_lib import (
    compute_metrics,
    safe_close,
    strat_buy_hold,
    strat_momentum,
)
from checking.tool_view_verify_hold_etf import get_group_lv2
from core.etf_data_fetcher import ETFDataFetcher

OUT_DIR = Path(__file__).resolve().parent / "out"
LOOKBACK_YEARS = 20

# Fine-grain grid around winners (mom_63_skip5_th0p0, mom_63_skip5_th1p0)
FINE_LOOKBACK = [55, 60, 63, 66, 70]
FINE_SKIP = [3, 4, 5, 6, 7]
FINE_THRESHOLD = [0.0, 0.25, 0.5, 0.75, 1.0]


def build_fine_variants() -> list[tuple[str, dict]]:
    """(variant_key, params) for strat_momentum."""
    out = []
    for lb in FINE_LOOKBACK:
        for sk in FINE_SKIP:
            for th in FINE_THRESHOLD:
                key = f"mom_{lb}_skip{sk}_th{str(th).replace('.', 'p')}"
                out.append((key, {"lookback_days": lb, "skip_recent_days": sk, "threshold_pct": th}))
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    variants = build_fine_variants()
    print(f"Fine-grain momentum variants: {len(variants)}")

    fetcher = ETFDataFetcher(
        yaml_path=str(project_root / "data" / "etf-v3.yaml"),
        cache_dir=str(project_root / "cache"),
    )
    all_tickers = list(fetcher.tickers_map.keys())
    tickers = [
        t for t in all_tickers
        if (fetcher.get_ticker_info(t) or {}).get("group_key", "").split(".")[0] != "commodity"
    ]
    print(f"ETFs: {len(tickers)} (excl. commodity)")

    calendar_days = LOOKBACK_YEARS * 365 + 90
    print("Fetching history ...")
    history, fetch_errors = fetcher.fetch_history_days(calendar_days, tickers=tickers)
    print(f"Fetched {len(history)} tickers, {len(fetch_errors)} errors")

    # --- Phase 1: run fine grid, collect metrics ---
    rows = []
    for ticker, df in history.items():
        close = safe_close(df)
        if close is None:
            continue
        info = fetcher.get_ticker_info(ticker)
        group = get_group_lv2(info)
        for v_key, params in variants:
            try:
                equity = strat_momentum(close, **params)
                m = compute_metrics(equity)
                if m:
                    rows.append({
                        "ticker": ticker,
                        "group": group,
                        "variant": v_key,
                        "cagr_pct": m["cagr_pct"],
                        "sharpe": m["sharpe"],
                        "max_drawdown_pct": m["max_drawdown_pct"],
                    })
            except Exception:
                pass

    df_all = pd.DataFrame(rows)
    csv_path = OUT_DIR / "momentum_fine_results.csv"
    df_all.to_csv(csv_path, index=False)
    print(f"Saved {csv_path} ({len(df_all)} rows)")

    # --- Phase 2: top 5 by avg CAGR ---
    if df_all.empty:
        print("No results; cannot compute top5.")
        return

    baseline_csv = project_root / "result" / "alice_checking" / "buy_hold_baseline.csv"
    if baseline_csv.exists():
        bl = pd.read_csv(baseline_csv)
        baseline_cagr = bl["cagr_pct"].mean()
    else:
        baseline_cagr = 7.0

    var_avg = (
        df_all.groupby("variant")
        .agg(avg_cagr=("cagr_pct", "mean"), avg_sharpe=("sharpe", "mean"))
        .reset_index()
    )
    var_avg = var_avg.sort_values("avg_cagr", ascending=False)
    top5 = var_avg.head(5)["variant"].tolist()
    top5_params = []
    for v_key in top5:
        for k, p in variants:
            if k == v_key:
                top5_params.append((k, p))
                break

    top5_path = OUT_DIR / "top5_variants.json"
    top5_path.write_text(json.dumps({"top5": top5, "baseline_avg_cagr": baseline_cagr}, indent=2), encoding="utf-8")
    print(f"Top 5 variants: {top5}")
    print(f"Saved {top5_path}")

    # --- Phase 3: equity curves for buy_hold + top5 ---
    strategies = [("buy_hold", strat_buy_hold, {})] + [(k, strat_momentum, p) for k, p in top5_params]
    curve_rows = []
    for ticker, df in history.items():
        close = safe_close(df)
        if close is None:
            continue
        for name, fn, kwargs in strategies:
            try:
                if name == "buy_hold":
                    equity = fn(close)
                else:
                    equity = fn(close, **kwargs)
                if equity is not None and not equity.empty:
                    for ts, val in equity.items():
                        curve_rows.append({"date": ts, "ticker": ticker, "strategy": name, "equity": float(val)})
            except Exception:
                pass

    curves_df = pd.DataFrame(curve_rows)
    if not curves_df.empty:
        curves_df["date"] = pd.to_datetime(curves_df["date"], utc=True)
    curves_path = OUT_DIR / "equity_curves.csv"
    curves_df.to_csv(curves_path, index=False)
    print(f"Saved {curves_path} ({len(curves_df)} rows)")

    # --- Phase 4: interactive HTML (Plotly) ---
    try:
        import plotly.graph_objects as go
    except ImportError:
        print("Plotly not installed; skip HTML. pip install plotly")
        return

    # Build one dropdown per ticker: equity over time for buy_hold + top5
    tickers_sorted = sorted(curves_df["ticker"].unique().tolist()) if not curves_df.empty else []
    if not tickers_sorted:
        print("No curve data for HTML.")
        return

    # Default: first ticker. We'll embed all tickers and use dropdown.
    fig = go.Figure()
    first_ticker = tickers_sorted[0]
    strat_order = ["buy_hold"] + top5
    colors = {"buy_hold": "black"}
    for i, s in enumerate(top5):
        colors[s] = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"][i % 5]

    for strat in strat_order:
        sub = curves_df[(curves_df["ticker"] == first_ticker) & (curves_df["strategy"] == strat)].sort_values("date")
        if sub.empty:
            continue
        # Use .tolist() for Plotly to avoid bdata serialization issues with pandas/numpy
        fig.add_trace(
            go.Scatter(
                x=sub["date"].dt.strftime("%Y-%m-%d").tolist(),
                y=sub["equity"].tolist(),
                name=strat,
                line=dict(color=colors.get(strat, "gray"), width=2 if strat == "buy_hold" else 1),
            )
        )

    fig.update_layout(
        title=f"Top 5 momentum vs buy_hold — {first_ticker} (select ticker below)",
        xaxis_title="Date",
        yaxis_title="Equity (start=1)",
        hovermode="x unified",
        height=500,
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
    )

    # Precompute per-ticker x/y for dropdown (one list per trace)
    # Plotly dropdown args: list of trace updates. So we need one button per ticker that updates all traces' x and y.
    # Better: use a single figure with one trace per (ticker, strategy) and use dropdown to set visible. That can be huge.
    # Simpler: one dropdown that replaces data for all traces. So we need to precompute for each ticker the arrays.
    ticker_data = {}
    for t in tickers_sorted:
        xs = {}
        ys = {}
        for strat in strat_order:
            sub = curves_df[(curves_df["ticker"] == t) & (curves_df["strategy"] == strat)].sort_values("date")
            xs[strat] = sub["date"].dt.strftime("%Y-%m-%d").tolist()
            ys[strat] = sub["equity"].tolist()
        ticker_data[t] = (xs, ys)

    # Build updatemenus: each button updates all 6 traces
    n_traces = len(strat_order)
    buttons = []
    for t in tickers_sorted:
        xs, ys = ticker_data[t]
        args_x = [xs.get(s, []) for s in strat_order]
        args_y = [ys.get(s, []) for s in strat_order]
        # args: [trace_update, layout_update]; trace update uses list per trace for x/y
        buttons.append(
            dict(
                label=t,
                method="update",
                args=[
                    {"x": args_x, "y": args_y},
                    {"title": f"Top 5 momentum vs buy_hold — {t}"},
                ],
            )
        )

    fig.update_layout(
        updatemenus=[
            dict(
                buttons=buttons,
                direction="down",
                showactive=True,
                x=0.0,
                xanchor="left",
                y=1.15,
                yanchor="top",
            )
        ],
    )

    html_path = OUT_DIR / "momentum_vs_buyhold.html"
    fig.write_html(str(html_path))
    print(f"Saved {html_path} (open in browser)")


if __name__ == "__main__":
    main()
