"""
ดึงข้อมูล ETF ย้อนหลัง 20 ปี จาก etf_data_fetcher แล้วแสดงกราฟ group by section (etf.yaml).
Section = ระดับบนของ etf.yaml: Commodity, Momentum, World, US Sectors
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from etf_data_fetcher import ETFDataFetcher

YEARS = 20
CALENDAR_DAYS = YEARS * 365 + 60


def get_section(group: str) -> str:
    """Map group from fetcher to top-level section (etf.yaml)."""
    top = (group or "").split(" - ")[0].strip()
    if top in ("Commodity", "Momentum", "US Sectors"):
        return top
    return "World"


def main():
    fetcher = ETFDataFetcher()
    tickers = list(fetcher.tickers_map.keys())
    if not tickers:
        print("No tickers from etf.yaml.")
        return

    print(f"Fetching {len(tickers)} tickers, {YEARS} years (~{CALENDAR_DAYS} calendar days)...")
    history, errors = fetcher.fetch_history_days(CALENDAR_DAYS, tickers=tickers)
    if errors:
        print(f"Errors ({len(errors)}): {list(errors.keys())[:10]}...")

    # Section -> list of (ticker, df)
    by_section: dict[str, list[tuple[str, pd.DataFrame]]] = {}
    for ticker, df in history.items():
        if df is None or df.empty or "Close" not in df.columns:
            continue
        info = fetcher.get_ticker_info(ticker)
        group = (info or {}).get("group") or "Unknown"
        section = get_section(group)
        by_section.setdefault(section, []).append((ticker, df))

    if not by_section:
        print("No history data to plot.")
        return

    # Normalize each series to 100 at first observation, then align to common index
    # Use union of all dates, forward-fill then take mean per section
    all_dates = None
    section_curves = {}

    for section, ticker_dfs in by_section.items():
        series_list = []
        for ticker, df in ticker_dfs:
            df = df.sort_index()
            close = df["Close"].dropna()
            if close.empty:
                continue
            norm = (close / close.iloc[0]) * 100.0
            series_list.append(norm)
        if not series_list:
            continue
        # Align: concat (union index), ffill then mean
        combined = pd.concat(series_list, axis=1, sort=True)
        combined = combined.sort_index().ffill().bfill()
        curve = combined.mean(axis=1)
        curve = curve.dropna()
        if curve.empty:
            continue
        section_curves[section] = curve
        if all_dates is None:
            all_dates = curve.index
        else:
            all_dates = all_dates.union(curve.index)

    if not section_curves:
        print("No section curves to plot.")
        return

    # Reindex each section to common index (all_dates), ffill, then plot
    common_index = all_dates.sort_values()
    colors = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    ]
    fig = go.Figure()
    for i, (section, curve) in enumerate(section_curves.items()):
        aligned = curve.reindex(common_index).ffill().bfill()
        aligned = aligned.dropna()
        if aligned.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=aligned.index,
                y=aligned.values,
                name=section,
                mode="lines",
                line=dict(width=1.5, color=colors[i % len(colors)]),
            )
        )

    fig.update_layout(
        title="ETF 20-year performance by section (normalized, mean within section)",
        xaxis_title="Date",
        yaxis_title="Normalized level (100 = start)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
        height=500,
    )
    out = Path(__file__).resolve().parent / "long_term_by_section.html"
    fig.write_html(str(out))
    print(f"Saved: {out}")
    fig.show()


if __name__ == "__main__":
    main()
