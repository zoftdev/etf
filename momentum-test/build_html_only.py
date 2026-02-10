"""Build momentum_vs_buyhold.html from existing out/ CSV and top5_variants.json."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

OUT_DIR = Path(__file__).resolve().parent / "out"

def main() -> None:
    curves_path = OUT_DIR / "equity_curves.csv"
    top5_path = OUT_DIR / "top5_variants.json"
    if not curves_path.exists() or not top5_path.exists():
        print("Run run_fine_grid.py first to generate out/equity_curves.csv and out/top5_variants.json")
        return
    top5 = json.loads(top5_path.read_text(encoding="utf-8"))["top5"]
    curves_df = pd.read_csv(curves_path)
    curves_df["date"] = pd.to_datetime(curves_df["date"], utc=True)
    strat_order = ["buy_hold"] + top5
    colors = {"buy_hold": "black"}
    for i, s in enumerate(top5):
        colors[s] = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"][i % 5]
    tickers_sorted = sorted(curves_df["ticker"].unique().tolist())
    first_ticker = tickers_sorted[0]
    fig = go.Figure()
    for strat in strat_order:
        sub = curves_df[(curves_df["ticker"] == first_ticker) & (curves_df["strategy"] == strat)].sort_values("date")
        if sub.empty:
            continue
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
    ticker_data = {}
    for t in tickers_sorted:
        xs, ys = {}, {}
        for strat in strat_order:
            sub = curves_df[(curves_df["ticker"] == t) & (curves_df["strategy"] == strat)].sort_values("date")
            xs[strat] = sub["date"].dt.strftime("%Y-%m-%d").tolist()
            ys[strat] = sub["equity"].tolist()
        ticker_data[t] = (xs, ys)
    buttons = []
    for t in tickers_sorted:
        xs, ys = ticker_data[t]
        args_x = [xs.get(s, []) for s in strat_order]
        args_y = [ys.get(s, []) for s in strat_order]
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
