#!/usr/bin/env python3
"""
Generate Plotly chart for momentum strategy results.

Usage:
  uv run python momentum-lab/gen_graph.py
  # Reads from result/momentum-lab/ (requires prior run_simulation)
  # Or import and call build_chart(sim_result, out_dir)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from simulate import ETFS, OUT_DIR, last_trading_day_of_month

# Optional: allow running standalone by loading saved data
RESULT_DIR = OUT_DIR


def build_chart(
    out_df: pd.DataFrame,
    holdings_history: list[dict],
    prices: pd.DataFrame,
    first_valid: pd.Timestamp | None,
    spread: float,
    spread_label: str,
    etfs: list[str] | None = None,
    out_path: Path | None = None,
) -> Path:
    """Build combined Plotly chart. Returns path to saved HTML."""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError as e:
        raise ImportError("Plotly required for gen_graph. pip install plotly") from e

    etfs = etfs or ETFS
    out_path = out_path or RESULT_DIR / "momentum_vs_buyhold.html"

    seen = set()
    month_end_dates = []
    for d in out_df.index:
        key = (d.year, d.month)
        if key in seen:
            continue
        last = last_trading_day_of_month(out_df, d.year, d.month)
        if last is not None and last in out_df.index:
            month_end_dates.append(last)
            seen.add(key)
    month_end_dates = sorted(set(month_end_dates))
    out_mo = out_df.loc[out_df.index.isin(month_end_dates)].sort_index()
    dates_str = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in out_mo.index]

    idx0 = prices.index.get_indexer([first_valid], method="ffill")[0]
    start_prices = prices.iloc[idx0]
    etf_norm_full = (prices / start_prices).reindex(out_df.index).ffill()
    etf_norm = etf_norm_full.loc[etf_norm_full.index.isin(month_end_dates)].sort_index()
    etf_dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in etf_norm.index]
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b",
              "#e377c2", "#7f7f7f", "#bcbd22", "#17becf", "#aec7e8", "#ffbb78", "#98df8a"]

    buy_x, buy_y, buy_text = [], [], []
    sell_x, sell_y, sell_text = [], [], []
    exits_detail_all: list[dict] = []
    JITTER = 0.008
    for h in holdings_history:
        d, dstr = h["date"], pd.Timestamp(h["date"]).strftime("%Y-%m-%d")
        mask = etf_norm_full.index <= d
        if not mask.any():
            continue
        row = etf_norm_full.loc[mask].iloc[-1]
        entries_list = [t for t in h["entries"] if t in etf_norm_full.columns and pd.notna(row.get(t))]
        for i, t in enumerate(entries_list):
            buy_x.append(dstr)
            buy_y.append(float(row[t]) + i * JITTER)
            buy_text.append(f"{t} buy")
        exits_det = h.get("exits_detail", [])
        for i, ed in enumerate(exits_det):
            t = ed["ticker"]
            if t in etf_norm_full.columns and pd.notna(row.get(t)):
                pnl = ed.get("pnl_pct", 0)
                win = "✓" if pnl > 0 else "✗"
                sell_x.append(dstr)
                sell_y.append(float(row[t]) - i * JITTER)
                sell_text.append(f"{t} sell • PnL: {win}{pnl:.1f}%")
        exits_detail_all.extend(exits_det)

    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=(
            "Equity curves",
            "All 13 ETFs (normalized) — ▲ buy, ▼ sell, dotted = round-trip",
        ),
        vertical_spacing=0.10,
        row_heights=[0.5, 0.5],
        shared_xaxes=True,
    )

    fig.add_trace(
        go.Scatter(x=dates_str, y=out_mo["momentum_spread0"].tolist(),
                  name="Momentum (spread=0%)", mode="lines+markers", marker=dict(size=4),
                  line=dict(color="#1f77b4", width=2)),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=dates_str, y=out_mo[spread_label].tolist(),
                  name=f"Momentum (spread={spread}%)", mode="lines+markers", marker=dict(size=4),
                  line=dict(color="#2ca02c", width=2)),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=dates_str, y=out_mo["buy_hold"].tolist(),
                  name="Buy-Hold", mode="lines+markers", marker=dict(size=4),
                  line=dict(color="#ff7f0e", width=2)),
        row=1, col=1,
    )

    buy_combined = ["<br>".join(buy_text[j] for j in range(len(buy_x)) if buy_x[j] == buy_x[i])
                    for i in range(len(buy_x))]
    sell_combined = ["<br>".join(sell_text[j] for j in range(len(sell_x)) if sell_x[j] == sell_x[i])
                     for i in range(len(sell_x))]
    if buy_x:
        fig.add_trace(
            go.Scatter(x=buy_x, y=buy_y, text=buy_combined, name="Buy", mode="markers",
                      marker=dict(symbol="triangle-up", size=8, color="green", line=dict(width=1)),
                      hovertemplate="%{text}<extra></extra>"),
            row=2, col=1,
        )
    if sell_x:
        fig.add_trace(
            go.Scatter(x=sell_x, y=sell_y, text=sell_combined, name="Sell", mode="markers",
                      marker=dict(symbol="triangle-down", size=8, color="red", line=dict(width=1)),
                      hovertemplate="%{text}<extra></extra>"),
            row=2, col=1,
        )
    for i, t in enumerate(etfs):
        if t not in etf_norm.columns:
            continue
        fig.add_trace(
            go.Scatter(x=etf_dates, y=etf_norm[t].tolist(), name=t,
                      mode="lines+markers", marker=dict(size=3),
                      line=dict(color=colors[i % len(colors)], width=1)),
            row=2, col=1,
        )

    for ed in exits_detail_all:
        t = ed["ticker"]
        if t not in start_prices.index or start_prices[t] <= 0:
            continue
        buy_d = pd.Timestamp(ed["buy_date"]).strftime("%Y-%m-%d")
        sell_d = pd.Timestamp(ed["sell_date"]).strftime("%Y-%m-%d")
        buy_yn = ed["buy_price"] / float(start_prices[t])
        sell_yn = ed["sell_price"] / float(start_prices[t])
        fig.add_trace(
            go.Scatter(x=[buy_d, sell_d], y=[buy_yn, sell_yn], mode="lines",
                      line=dict(color="rgba(128,128,128,0.4)", width=1, dash="dot"),
                      name=f"{t} round-trip", showlegend=False,
                      hovertemplate=f"{t} buy→sell PnL: {ed.get('pnl_pct',0):.1f}%<extra></extra>"),
            row=2, col=1,
        )

    for i, h in enumerate(holdings_history):
        if not h["short"]:
            continue
        dstr = pd.Timestamp(h["date"]).strftime("%Y-%m-%d")
        end_str = dates_str[-1] if dates_str else dstr
        if i + 1 < len(holdings_history):
            end_str = pd.Timestamp(holdings_history[i + 1]["date"]).strftime("%Y-%m-%d")
        fig.add_vrect(x0=dstr, x1=end_str, fillcolor="rgba(255,100,100,0.12)",
                      line_width=0, row=1, col=1)

    fig.add_annotation(
        text="<b>พื้นที่สีชมพู:</b> ช่วงที่เปิด short (correlation filter ผ่าน, 20d corr > 250d corr)",
        xref="paper", yref="paper",
        x=0.5, y=1.02, xanchor="center", yanchor="bottom",
        showarrow=False, font=dict(size=11),
    )

    fig.update_layout(
        title=dict(text=f"QuantPedia ETF Momentum (spread 0% vs {spread}%)", x=0.5, xanchor="center"),
        height=900,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        margin=dict(t=120),
        template="plotly_white",
    )
    fig.update_xaxes(title_text="Date", row=1, col=1)
    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_yaxes(title_text="Equity (start=1)", row=1, col=1)
    fig.update_yaxes(title_text="Price (start=1)", row=2, col=1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out_path))
    return out_path


def main() -> None:
    """Run standalone: run simulation then generate chart."""
    from simulate import run_simulation

    print("Running simulation...")
    result = run_simulation()
    print("Generating chart...")
    path = build_chart(
        result.out_df,
        result.holdings_history,
        result.prices,
        first_valid=result.first_valid,
        spread=result.spread,
        spread_label=result.spread_label,
        out_path=RESULT_DIR / "momentum_vs_buyhold.html",
    )
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
