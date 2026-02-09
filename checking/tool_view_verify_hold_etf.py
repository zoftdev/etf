"""tool_view_verify_hold_etf.py

Originally: verify buy&hold 20-year holding returns for ETFs.

Now: a small backtest harness to *compare strategies* on the same ETF universe.

Default behaviour remains comparable to the old script:
- strategy=buy_hold
- window ~20 years

Outputs:
- HTML dashboard in workspace/etf/result/
- CSV with per-ETF per-strategy metrics

Notes
- Uses Close column from fetched history.
- Metrics are time-weighted (equity-curve based).
- No fees/taxes/slippage.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.etf_data_fetcher import ETFDataFetcher
from checking.strategy_backtest_lib import available_strategies, compute_metrics, safe_close

DEFAULT_YEARS = 20


def get_group_lv2(info: dict | None) -> str:
    """Extract lv2 group from group_key (e.g. world.asia_pacific -> asia_pacific)."""
    if not info:
        return "unknown"
    key = (info.get("group_key") or "").strip()
    if not key:
        return "unknown"
    parts = key.split(".")
    return parts[1] if len(parts) >= 2 else parts[0]


# ----------------------------
# Main
# ----------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    strategies = ",".join(available_strategies().keys())

    p = argparse.ArgumentParser(description="Compare ETF strategy performance (time-weighted).")
    p.add_argument("--years", type=int, default=DEFAULT_YEARS, help="Lookback window in years (approx).")
    p.add_argument(
        "--strategies",
        type=str,
        default="buy_hold",
        help=f"Comma-separated strategy keys. Available: {strategies}",
    )
    p.add_argument(
        "--out",
        type=str,
        default="verify_hold_etf",
        help="Output base filename (without extension) in result/",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    strat_map = available_strategies()
    selected_keys = [s.strip() for s in (args.strategies or "").split(",") if s.strip()]
    unknown = [k for k in selected_keys if k not in strat_map]
    if unknown:
        raise SystemExit(f"Unknown strategies: {unknown}. Available: {list(strat_map.keys())}")

    selected = [strat_map[k] for k in selected_keys]

    fetcher = ETFDataFetcher()
    tickers = list(fetcher.tickers_map.keys())
    if not tickers:
        print("No tickers from etf.yaml.")
        return

    calendar_days = args.years * 365 + max(30, args.years * 3)
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
        group_lv2 = get_group_lv2(info)

        for strat in selected:
            try:
                equity = strat.fn(close)
            except Exception as e:
                print(f"Strategy {strat.key} failed for {ticker}: {e}")
                continue

            metrics = compute_metrics(equity)
            if not metrics:
                continue

            rows.append(
                {
                    "ticker": ticker,
                    "group": group_lv2,
                    "strategy": strat.key,
                    "strategy_name": strat.name,
                    **metrics,
                }
            )

    if not rows:
        print("No valid results to display.")
        return

    df_all = pd.DataFrame(rows)

    # Overall stats print (like the old script)
    print("\n=== Overall Statistics (CAGR) ===")
    for strat in selected:
        sub = df_all[df_all["strategy"] == strat.key]
        if sub.empty:
            continue
        print(
            f"{strat.key}: ETFs={len(sub)} | Avg CAGR={sub['cagr_pct'].mean():.2f}% | "
            f"Median CAGR={sub['cagr_pct'].median():.2f}% | Avg Total Return={sub['total_return_pct'].mean():.2f}%"
        )

    # ----------------------------
    # Plots
    # ----------------------------

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=(
            "CAGR Distribution (Box) by Strategy",
            "Average Metrics by Strategy",
            "Top 20 ETFs by CAGR (select strategy)",
            "Max Drawdown Distribution by Strategy",
        ),
        specs=[[{"type": "box"}, {"type": "bar"}], [{"type": "bar"}, {"type": "box"}]],
        vertical_spacing=0.14,
        horizontal_spacing=0.10,
    )

    # (1) Box: CAGR by strategy
    for strat in selected:
        sub = df_all[df_all["strategy"] == strat.key]
        fig.add_trace(
            go.Box(
                y=sub["cagr_pct"].tolist(),
                name=strat.key,
                boxmean=True,
                hovertemplate=f"<b>{strat.key}</b><br>CAGR: %{{y:.2f}}%<extra></extra>",
            ),
            row=1,
            col=1,
        )

    # (2) Bar: avg CAGR + avg MDD (secondary scale is overkill in subplots; keep two bars per strat)
    avg_by = (
        df_all.groupby(["strategy", "strategy_name"], as_index=False)
        .agg(avg_cagr_pct=("cagr_pct", "mean"), avg_mdd_pct=("max_drawdown_pct", "mean"), count=("ticker", "count"))
        .sort_values("avg_cagr_pct", ascending=False)
    )

    fig.add_trace(
        go.Bar(
            x=avg_by["strategy"].tolist(),
            y=avg_by["avg_cagr_pct"].tolist(),
            name="Avg CAGR %",
            marker=dict(color="#2E7D32"),
            text=[f"{x:.2f}%" for x in avg_by["avg_cagr_pct"].tolist()],
            textposition="outside",
            hovertemplate="Strategy=%{x}<br>Avg CAGR=%{y:.2f}%<extra></extra>",
        ),
        row=1,
        col=2,
    )

    fig.add_trace(
        go.Bar(
            x=avg_by["strategy"].tolist(),
            y=avg_by["avg_mdd_pct"].tolist(),
            name="Avg Max Drawdown %",
            marker=dict(color="#C62828"),
            text=[f"{x:.2f}%" for x in avg_by["avg_mdd_pct"].tolist()],
            textposition="outside",
            hovertemplate="Strategy=%{x}<br>Avg MDD=%{y:.2f}%<extra></extra>",
        ),
        row=1,
        col=2,
    )

    # (3) Top 20 tickers by CAGR with dropdown per strategy
    # create one trace per strategy; only show first by default
    top_traces = []
    for i, strat in enumerate(selected):
        sub = df_all[df_all["strategy"] == strat.key].copy()
        sub = sub.sort_values("cagr_pct", ascending=False).head(20).sort_values("cagr_pct", ascending=True)
        trace = go.Bar(
            y=sub["ticker"].tolist(),
            x=sub["cagr_pct"].tolist(),
            name=f"Top 20 ({strat.key})",
            orientation="h",
            visible=(i == 0),
            marker=dict(color="#1565C0"),
            text=[f"{x:.2f}%" for x in sub["cagr_pct"].tolist()],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>CAGR: %{x:.2f}%<extra></extra>",
        )
        top_traces.append(trace)
        fig.add_trace(trace, row=2, col=1)

    # (4) Box: Max drawdown by strategy
    for strat in selected:
        sub = df_all[df_all["strategy"] == strat.key]
        fig.add_trace(
            go.Box(
                y=sub["max_drawdown_pct"].tolist(),
                name=strat.key,
                boxmean=True,
                hovertemplate=f"<b>{strat.key}</b><br>Max DD: %{{y:.2f}}%<extra></extra>",
            ),
            row=2,
            col=2,
        )

    # Dropdown to toggle top20 panel traces
    # Need to toggle visibility for those traces only; they are placed after earlier traces.
    n_traces_before_top = len(selected) + 2  # box traces + two avg bars
    top_start = n_traces_before_top
    top_end = top_start + len(selected)
    # drawdown boxes added after top20, ignore

    buttons = []
    for i, strat in enumerate(selected):
        vis = [True] * len(fig.data)
        # top20 traces visibility set so only i is True
        for j in range(top_start, top_end):
            vis[j] = (j == top_start + i)
        buttons.append(
            dict(
                label=strat.key,
                method="update",
                args=[{"visible": vis}, {"title": fig.layout.title.text}],
            )
        )

    fig.update_layout(
        title=dict(
            text=f"ETF Strategy Compare ({args.years}Y window)<br><sub>Total rows: {len(df_all)} (ETF×strategy)</sub>",
            x=0.5,
            xanchor="center",
        ),
        height=1100,
        barmode="group",
        hovermode="closest",
        updatemenus=[
            dict(
                type="dropdown",
                x=0.40,
                y=0.46,
                xanchor="left",
                yanchor="top",
                buttons=buttons,
                showactive=True,
                bgcolor="white",
                bordercolor="#ccc",
                borderwidth=1,
            )
        ],
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=40, t=110, b=40),
    )

    fig.update_xaxes(title_text="CAGR (%)", row=2, col=1)
    fig.update_xaxes(title_text="%", row=1, col=2)
    fig.update_yaxes(title_text="CAGR (%)", row=1, col=1)
    fig.update_yaxes(title_text="Max Drawdown (%)", row=2, col=2)

    # ----------------------------
    # HTML + CSV output
    # ----------------------------

    result_dir = Path(__file__).resolve().parent.parent / "result"
    result_dir.mkdir(parents=True, exist_ok=True)
    out_base = args.out

    # table: make it easy to scan
    df_table = df_all.copy()
    df_table["start_date"] = df_table["start_date"].dt.strftime("%Y-%m-%d")
    df_table["end_date"] = df_table["end_date"].dt.strftime("%Y-%m-%d")
    df_table = df_table.sort_values(["strategy", "cagr_pct"], ascending=[True, False])

    # Save CSV
    csv_file = result_dir / f"{out_base}.csv"
    df_table.to_csv(csv_file, index=False)

    # Embed Plotly
    fig_json = fig.to_json()

    # Small HTML wrapper
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset=\"utf-8\" />
        <title>ETF Strategy Compare</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
            .container {{ max-width: 1500px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }}
            h1 {{ margin: 0 0 10px 0; }}
            .meta {{ color: #555; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 18px; font-size: 13px; }}
            th, td {{ padding: 10px; border-bottom: 1px solid #eee; text-align: left; }}
            th {{ background: #222; color: white; position: sticky; top: 0; }}
            tr:hover {{ background: #fafafa; }}
            .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
        </style>
    </head>
    <body>
      <div class=\"container\">
        <h1>ETF Strategy Compare</h1>
        <div class=\"meta\">
          Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>
          Window: ~{args.years} years | Strategies: {', '.join([s.key for s in selected])}
        </div>

        <div id=\"charts\"></div>

        <h2>Results Table (ETF × Strategy)</h2>
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Group</th>
              <th>Strategy</th>
              <th class=\"num\">CAGR %</th>
              <th class=\"num\">Total Return %</th>
              <th class=\"num\">Max DD %</th>
              <th class=\"num\">Vol (ann) %</th>
              <th class=\"num\">Sharpe</th>
              <th class=\"num\">Years</th>
              <th>Start</th>
              <th>End</th>
            </tr>
          </thead>
          <tbody>
    """

    for _, r in df_table.iterrows():
        html_content += f"""
            <tr>
              <td><b>{r['ticker']}</b></td>
              <td>{r['group']}</td>
              <td>{r['strategy']}</td>
              <td class=\"num\">{r['cagr_pct']:.2f}</td>
              <td class=\"num\">{r['total_return_pct']:.2f}</td>
              <td class=\"num\">{r['max_drawdown_pct']:.2f}</td>
              <td class=\"num\">{'' if pd.isna(r['vol_ann_pct']) else f"{r['vol_ann_pct']:.2f}"}</td>
              <td class=\"num\">{'' if pd.isna(r['sharpe']) else f"{r['sharpe']:.2f}"}</td>
              <td class=\"num\">{r['years']:.2f}</td>
              <td>{r['start_date']}</td>
              <td>{r['end_date']}</td>
            </tr>
        """

    html_content += f"""
          </tbody>
        </table>

      </div>

      <script src=\"https://cdn.plot.ly/plotly-latest.min.js\"></script>
      <script>
        var figure = {fig_json};
        Plotly.newPlot('charts', figure.data, figure.layout, {{responsive: true}});
      </script>
    </body>
    </html>
    """

    html_file = result_dir / f"{out_base}.html"
    html_file.write_text(html_content, encoding="utf-8")

    print(f"\nSaved: {html_file}")
    print("Open in browser to view interactive dashboard")
    print(f"Saved CSV: {csv_file}")


if __name__ == "__main__":
    main()
