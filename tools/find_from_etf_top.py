#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml


@dataclass(frozen=True)
class TickerMeta:
    category: str  # "country" | "commodity" | "us:sector"
    segment: str   # e.g. country name / commodity segment / sector name
    name: str      # ETF name


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _collect_tickers_from_v3(y: dict) -> tuple[dict[str, TickerMeta], dict[str, list[str]]]:
    """
    Returns:
      - meta_by_ticker: ticker -> TickerMeta (best-effort; if duplicates exist, first wins)
      - tickers_by_category: { "country": [...], "commodity": [...], "us:sector": [...] }
    """
    etfs = (y or {}).get("etfs", {})

    meta_by_ticker: dict[str, TickerMeta] = {}
    tickers_by_category: dict[str, list[str]] = {"country": [], "commodity": [], "us:sector": []}

    def add(category: str, tickers: list[str], segment: str, name: str):
        for t in tickers:
            if t not in meta_by_ticker:
                meta_by_ticker[t] = TickerMeta(category=category, segment=segment, name=name or "")
            tickers_by_category[category].append(t)

    # Commodity
    for item in etfs.get("commodity", {}).get("items", []) or []:
        add(
            category="commodity",
            tickers=list(item.get("tickers") or []),
            segment=str(item.get("segment") or ""),
            name=str(item.get("name") or ""),
        )

    # US Sectors
    for item in etfs.get("us_sectors", {}).get("items", []) or []:
        add(
            category="us:sector",
            tickers=list(item.get("tickers") or []),
            segment=str(item.get("segment") or ""),
            name=str(item.get("name") or ""),
        )

    # Country/World (all world_* groups in v3)
    for key, group in (etfs or {}).items():
        if not str(key).startswith("world_"):
            continue
        for item in (group or {}).get("items", []) or []:
            add(
                category="country",
                tickers=list(item.get("tickers") or []),
                segment=str(item.get("segment") or ""),
                name=str(item.get("name") or ""),
            )

    # De-dup while preserving order
    for k, v in tickers_by_category.items():
        seen: set[str] = set()
        deduped: list[str] = []
        for t in v:
            if t in seen:
                continue
            seen.add(t)
            deduped.append(t)
        tickers_by_category[k] = deduped

    return meta_by_ticker, tickers_by_category


def _first_last_valid(s: pd.Series) -> tuple[pd.Timestamp | None, float | None, pd.Timestamp | None, float | None]:
    s2 = s.dropna()
    if s2.empty:
        return None, None, None, None
    first_idx = s2.index[0]
    last_idx = s2.index[-1]
    return first_idx, float(s2.iloc[0]), last_idx, float(s2.iloc[-1])


def _annual_returns(
    prices: pd.DataFrame, tickers: list[str], meta_by_ticker: dict[str, TickerMeta], category: str, top_n: int
) -> pd.DataFrame:
    available = [t for t in tickers if t in prices.columns]
    df = prices[available].copy()

    rows: list[dict] = []
    for year, g in df.groupby(df.index.year):
        perf_rows: list[dict] = []
        for t in available:
            start_dt, start_px, end_dt, end_px = _first_last_valid(g[t])
            if start_px is None or end_px is None or start_px == 0:
                continue
            r = (end_px / start_px) - 1.0
            m = meta_by_ticker.get(t, TickerMeta(category=category, segment="", name=""))
            perf_rows.append(
                dict(
                    year=int(year),
                    ticker=t,
                    segment=m.segment,
                    name=m.name,
                    return_=float(r),
                    start_date=str(start_dt.date()),
                    start_price=float(start_px),
                    end_date=str(end_dt.date()),
                    end_price=float(end_px),
                )
            )

        if not perf_rows:
            continue

        year_df = pd.DataFrame(perf_rows).sort_values(["return_", "ticker"], ascending=[False, True]).head(top_n)
        year_df.insert(1, "rank", range(1, len(year_df) + 1))
        rows.append(year_df)

    if not rows:
        return pd.DataFrame(
            columns=["year", "rank", "ticker", "segment", "name", "return_", "start_date", "start_price", "end_date", "end_price"]
        )

    out = pd.concat(rows, ignore_index=True).sort_values(["year", "rank"], ascending=[True, True])
    return out


def _fmt_pct(x: float) -> str:
    v = x * 100.0
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


def _write_markdown(report_df: pd.DataFrame, out_path: Path, title: str):
    lines: list[str] = []
    lines.append(f"## {title}")
    lines.append("")
    if report_df.empty:
        lines.append("_No data._")
        lines.append("")
        out_path.write_text("\n".join(lines), encoding="utf-8")
        return

    for year, g in report_df.groupby("year", sort=True):
        lines.append(f"### {int(year)}")
        lines.append("")
        lines.append("| Rank | Ticker | Segment | Return | Start | End |")
        lines.append("|---:|---|---|---:|---|---|")
        for _, r in g.sort_values("rank").iterrows():
            lines.append(
                f"| {int(r['rank'])} | {r['ticker']} | {r.get('segment','')} | {_fmt_pct(float(r['return_']))} | "
                f"{r['start_date']} ({float(r['start_price']):.2f}) | {r['end_date']} ({float(r['end_price']):.2f}) |"
            )
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Find top N ETF performance per year by category.")
    ap.add_argument("--prices", default="data/etf_price.csv", help="Path to wide price CSV (Date + tickers columns).")
    ap.add_argument("--universe", default="data/etf-v3.yaml", help="Path to ETF universe YAML (v3).")
    ap.add_argument("--out", default="find-from-etf-top", help="Output directory.")
    ap.add_argument("--top", type=int, default=5, help="Top N per year.")
    args = ap.parse_args()

    prices_path = Path(args.prices)
    universe_path = Path(args.universe)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    y = _load_yaml(universe_path)
    meta_by_ticker, tickers_by_category = _collect_tickers_from_v3(y)

    prices = pd.read_csv(prices_path, parse_dates=["Date"])
    prices = prices.set_index("Date").sort_index()

    # Ensure numeric
    for c in prices.columns:
        prices[c] = pd.to_numeric(prices[c], errors="coerce")

    reports: dict[str, pd.DataFrame] = {}
    reports["country"] = _annual_returns(prices, tickers_by_category["country"], meta_by_ticker, "country", args.top)
    reports["commodity"] = _annual_returns(prices, tickers_by_category["commodity"], meta_by_ticker, "commodity", args.top)
    reports["us:sector"] = _annual_returns(prices, tickers_by_category["us:sector"], meta_by_ticker, "us:sector", args.top)

    # Write machine-readable CSV too (small and useful)
    for key, df in reports.items():
        df.to_csv(out_dir / f"top{args.top}_{key.replace(':','_')}_by_year.csv", index=False)

    # Write human-readable Markdown
    _write_markdown(reports["country"], out_dir / f"top{args.top}_country_by_year.md", "Top 5 Country/World ETFs by Year")
    _write_markdown(reports["commodity"], out_dir / f"top{args.top}_commodity_by_year.md", "Top 5 Commodity ETFs by Year")
    _write_markdown(reports["us:sector"], out_dir / f"top{args.top}_us_sector_by_year.md", "Top 5 US Sector ETFs by Year")


if __name__ == "__main__":
    main()

