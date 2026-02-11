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

from simulate import DEFAULT_ETFS, OUT_DIR, last_trading_day_of_month

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
    """Build 3-row Plotly chart: equity curves, holdings heatmap, exit P&L."""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError as e:
        raise ImportError("Plotly required for gen_graph. pip install plotly") from e

    etfs = etfs or DEFAULT_ETFS
    if out_path is None:
        out_path = RESULT_DIR / "from-research" / "momentum_vs_buyhold.html"

    # ── Shared x-axis: use holdings_history rebalance dates for all 3 rows ──
    h_timestamps = [pd.Timestamp(h["date"]) for h in holdings_history]
    h_dates = [d.strftime("%Y-%m-%d") for d in h_timestamps]
    # Resample equity curves at rebalance dates (ffill to nearest prior date)
    out_mo = out_df.reindex(h_timestamps, method="ffill")

    # ── Holdings matrix: z[etf_i][month_j] = 1(LONG), -1(SHORT), 0(none) ──
    n_etfs = len(etfs)
    n_months = len(holdings_history)
    z = [[0.0] * n_months for _ in range(n_etfs)]
    hover = [[""] * n_months for _ in range(n_etfs)]

    for j, h in enumerate(holdings_history):
        dstr = h_dates[j]
        longs_set = set(h.get("longs", []))
        short_t = h.get("short")
        entries_set = set(h.get("entries", []))
        exits_map = {ed["ticker"]: ed for ed in h.get("exits_detail", [])}

        for i, etf in enumerate(etfs):
            parts = [f"<b>{etf}</b> | {dstr}"]
            if etf in longs_set:
                z[i][j] = 1.0
                tag = "LONG 25%"
                if etf in entries_set:
                    tag += "  ← new"
                parts.append(tag)
            elif short_t == etf:
                z[i][j] = -1.0
                tag = "SHORT 30%"
                if etf in entries_set:
                    tag += "  ← new"
                parts.append(tag)
            else:
                parts.append("—")
            if etf in exits_map:
                ed = exits_map[etf]
                pnl = ed["pnl_pct"]
                hold = (pd.Timestamp(ed["sell_date"]) - pd.Timestamp(ed["buy_date"])).days
                parts.append(f"CLOSED {pnl:+.1f}% ({hold}d hold)")
            hover[i][j] = "<br>".join(parts)

    # ── Exit P&L data ──
    exit_dates: list[str] = []
    exit_pnls: list[float] = []
    exit_colors: list[str] = []
    exit_symbols: list[str] = []
    exit_hover: list[str] = []
    for j, h in enumerate(holdings_history):
        dstr = pd.Timestamp(h["date"]).strftime("%Y-%m-%d")
        prev_h = holdings_history[j - 1] if j > 0 else None
        for ed in h.get("exits_detail", []):
            t = ed["ticker"]
            pnl = ed["pnl_pct"]
            hold = (pd.Timestamp(ed["sell_date"]) - pd.Timestamp(ed["buy_date"])).days
            side = "SHORT" if prev_h and prev_h.get("short") == t else "LONG"
            exit_dates.append(dstr)
            exit_pnls.append(pnl)
            exit_colors.append("#27ae60" if pnl > 0 else "#e74c3c")
            exit_symbols.append("diamond" if side == "SHORT" else "circle")
            exit_hover.append(
                f"<b>{t}</b> ({side})<br>"
                f"P&L: {pnl:+.1f}%<br>"
                f"Hold: {hold}d<br>"
                f"Exit: {dstr}"
            )

    # ── Build 3-row figure ──
    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=(
            "Equity Curves",
            "Monthly Holdings — "
            "<span style='color:#27ae60'>■ LONG</span>  "
            "<span style='color:#e74c3c'>■ SHORT</span>  "
            "<span style='color:#ddd'>■ not held</span>",
            "Closed Position P&L (%) — "
            "<span style='color:#27ae60'>● long exit</span>  "
            "<span style='color:#e74c3c'>◆ short exit</span>",
        ),
        vertical_spacing=0.07,
        row_heights=[0.33, 0.37, 0.30],
        shared_xaxes=True,
    )

    # ── Row 1: Equity curves ──
    fig.add_trace(go.Scatter(
        x=h_dates, y=out_mo["momentum_spread0"].tolist(),
        name="Momentum (spread=0%)", mode="lines+markers",
        marker=dict(size=3), line=dict(color="#1f77b4", width=2),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=h_dates, y=out_mo[spread_label].tolist(),
        name=f"Momentum (spread={spread}%)", mode="lines+markers",
        marker=dict(size=3), line=dict(color="#2ca02c", width=2),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=h_dates, y=out_mo["buy_hold"].tolist(),
        name="Buy-Hold", mode="lines+markers",
        marker=dict(size=3), line=dict(color="#ff7f0e", width=2),
    ), row=1, col=1)

    # Short-period pink shading on equity chart
    for i, h in enumerate(holdings_history):
        if not h.get("short"):
            continue
        dstr = h_dates[i]
        end_str = h_dates[-1] if i + 1 >= len(holdings_history) else h_dates[i + 1]
        fig.add_vrect(x0=dstr, x1=end_str, fillcolor="rgba(255,100,100,0.12)",
                      line_width=0, row=1, col=1)

    # ── Row 2: Holdings heatmap ──
    colorscale = [
        [0.0, "#e74c3c"],
        [0.5, "#f0f0f0"],
        [1.0, "#27ae60"],
    ]
    fig.add_trace(go.Heatmap(
        z=z, x=h_dates, y=etfs,
        colorscale=colorscale, zmin=-1, zmax=1,
        showscale=False,
        hovertext=hover,
        hovertemplate="%{hovertext}<extra></extra>",
        xgap=1, ygap=2,
    ), row=2, col=1)

    # ── Row 3: Exit P&L scatter ──
    if exit_dates:
        fig.add_trace(go.Scatter(
            x=exit_dates, y=exit_pnls,
            mode="markers",
            marker=dict(
                size=7, color=exit_colors, symbol=exit_symbols,
                line=dict(width=0.5, color="white"),
            ),
            text=exit_hover,
            hovertemplate="%{text}<extra></extra>",
            name="Exit P&L",
        ), row=3, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="gray",
                      line_width=1, row=3, col=1)

    # ── Layout ──
    fig.add_annotation(
        text="Pink shade = short hedge active (20d corr > 250d corr)",
        xref="paper", yref="paper",
        x=0.5, y=1.01, xanchor="center", yanchor="bottom",
        showarrow=False, font=dict(size=10, color="gray"),
    )
    fig.update_layout(
        title=dict(
            text=f"QuantPedia ETF Momentum Strategy (spread 0% vs {spread}%)",
            x=0.5, xanchor="center",
        ),
        height=1100,
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.03,
                    xanchor="center", x=0.5),
        margin=dict(t=130, b=40),
        template="plotly_white",
    )
    fig.update_xaxes(title_text="", row=1, col=1)
    fig.update_xaxes(title_text="", row=2, col=1)
    fig.update_xaxes(title_text="Date", row=3, col=1)
    fig.update_yaxes(title_text="Equity", row=1, col=1)
    fig.update_yaxes(autorange="reversed", row=2, col=1)
    fig.update_yaxes(title_text="P&L %", row=3, col=1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out_path))
    return out_path


def main() -> None:
    """Run standalone: run simulation then generate chart."""
    from simulate import default_config, run_simulation

    print("Running simulation...")
    result = run_simulation()
    cfg = result.config
    print("Generating chart...")
    path = build_chart(
        result.out_df,
        result.holdings_history,
        result.prices,
        first_valid=result.first_valid,
        spread=result.spread,
        spread_label=result.spread_label,
        etfs=cfg.etfs,
        out_path=cfg.result_dir() / "momentum_vs_buyhold.html",
    )
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
