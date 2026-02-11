#!/usr/bin/env python3
"""
Execute 5 ETF selection plans and record results.
Plans defined in plans.md - each has different focus but follows select-etf.md criteria.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
import yfinance as yf

OUT_DIR = Path(__file__).resolve().parent

# Candidates from select-etf.md
CANDIDATES = {
    "us_equity": ["SPY", "QQQ", "IWM", "IYR", "VTV", "MTUM"],
    "intl_equity": ["EFA", "EEM", "VEU"],
    "bonds": ["TLT", "IEF", "LQD", "TIP", "HYG"],
    "commodities": ["GLD", "SLV", "USO", "DBC"],
    "currency": ["FXE", "UUP"],
    "sector": ["XLU", "XLF", "XLE", "XLK", "XLV", "XLI"],  # for Plan E
}

# QuantPedia default 13
QUANTPEDIA_13 = [
    "SPY", "IWM", "EFA", "EEM", "IYR", "QQQ",
    "LQD", "IEF", "TIP",
    "GLD", "USO", "DBC",
    "FXE",
]


@dataclass
class ETFInfo:
    ticker: str
    name: str
    aum_m: float | None
    volume: float | None
    expense_ratio: float | None
    inception: str | None
    category: str
    has_15y_data: bool = False
    first_date: str | None = None

    @property
    def age_years(self) -> float | None:
        if not self.inception:
            return None
        try:
            d = datetime.strptime(self.inception[:10], "%Y-%m-%d")
            return (datetime.now() - d).days / 365.25
        except Exception:
            return None

    def passes_basic(self, min_aum_m: float = 500, min_volume: float = 500_000, min_age: float = 5, max_er: float = 0.5) -> bool:
        if self.aum_m is not None and self.aum_m < min_aum_m:
            return False
        if self.volume is not None and self.volume < min_volume:
            return False
        if self.age_years is not None and self.age_years < min_age:
            return False
        if self.expense_ratio is not None and self.expense_ratio > max_er:
            return False
        return True


def fetch_etf_info(ticker: str, category: str) -> ETFInfo | None:
    """Fetch ETF metadata from yfinance."""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        aum = info.get("totalAssets") or info.get("aum")
        if aum:
            aum = float(aum) / 1e6
        vol = info.get("averageVolume") or info.get("volume")
        er = info.get("expenseRatio")
        inc = info.get("fundInception")
        name = info.get("longName") or info.get("shortName") or ticker
        return ETFInfo(
            ticker=ticker,
            name=str(name)[:60],
            aum_m=float(aum) if aum else None,
            volume=float(vol) if vol else None,
            expense_ratio=float(er) if er is not None else None,
            inception=str(inc) if inc else None,
            category=category,
        )
    except Exception:
        return None


def fetch_all_info() -> dict[str, ETFInfo]:
    """Fetch info for all candidates."""
    result: dict[str, ETFInfo] = {}
    for cat, tickers in CANDIDATES.items():
        for t in tickers:
            if t not in result:
                info = fetch_etf_info(t, cat)
                if info:
                    result[t] = info
    return result


def fetch_prices(tickers: list[str], years: int) -> pd.DataFrame:
    """Fetch adjusted close prices."""
    days = years * 365 + 60
    end = pd.Timestamp.now().normalize()
    start = end - pd.Timedelta(days=days)
    data = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False, threads=True)
    if len(tickers) == 1:
        df = data[["Close"]].rename(columns={"Close": tickers[0]})
    elif isinstance(data.columns, pd.MultiIndex):
        df = data.xs("Close", axis=1, level=0).copy()
    else:
        df = data[["Close"]].copy() if "Close" in data.columns else data.copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df.sort_index().dropna(how="all")
    return df


def compute_avg_pairwise_corr(returns: pd.DataFrame, tickers: list[str]) -> float:
    """Average pairwise correlation (excl diagonal)."""
    sub = returns[tickers].dropna(how="all").dropna(axis=1)
    if len(sub) < 60 or len(sub.columns) < 2:
        return float("nan")
    c = sub.corr().values
    n = c.shape[0]
    mask = ~np.eye(n, dtype=bool)
    return float(np.nanmean(c[mask]))


def greedy_low_correlation(returns: pd.DataFrame, by_class: dict[str, list[str]], n_total: int = 13) -> list[str]:
    """Select n_total ETFs greedily to minimize avg pairwise correlation, with min per class."""
    selected: list[str] = []
    all_tickers = [t for tickers in by_class.values() for t in tickers]
    valid_tickers = [t for t in all_tickers if t in returns.columns]

    def score_add(t: str) -> float:
        cand = selected + [t]
        c = compute_avg_pairwise_corr(returns, cand)
        return c if not np.isnan(c) else 1.0

    # Seed: pick first 2 from different classes so corr is defined
    for cat, tickers in by_class.items():
        for t in tickers:
            if t in valid_tickers and t not in selected:
                selected.append(t)
                break
        if len(selected) >= 2:
            break
    if len(selected) < 2:
        selected.extend([t for t in valid_tickers if t not in selected][: 2 - len(selected)])

    # Phase 1: ensure min 2 per class
    for cat, tickers in by_class.items():
        in_cat = [t for t in tickers if t in valid_tickers and t not in selected]
        count_in = sum(1 for t in selected if t in tickers)
        for _ in range(min(2 - count_in, len(in_cat))):
            best_t = min(in_cat, key=score_add)
            selected.append(best_t)
            in_cat.remove(best_t)

    # Phase 2: fill to n_total by lowest corr
    while len(selected) < n_total:
        remaining = [t for t in valid_tickers if t not in selected]
        if not remaining:
            break
        best_t = min(remaining, key=score_add)
        selected.append(best_t)

    return selected[:n_total]


# --- Plan implementations ---

def plan_a_quantpedia_classic(info_map: dict[str, ETFInfo]) -> list[str]:
    """Plan A: Use QuantPedia 13, filter by basic criteria where possible."""
    out = []
    for t in QUANTPEDIA_13:
        if t in info_map and info_map[t].passes_basic(min_aum_m=200, min_volume=200_000, min_age=3):
            out.append(t)
        elif t in info_map:
            out.append(t)  # include anyway if in QuantPedia
    return out[:13] if len(out) >= 13 else QUANTPEDIA_13


def plan_b_low_correlation(info_map: dict[str, ETFInfo], prices: pd.DataFrame) -> list[str]:
    """Plan B: Greedy low correlation selection."""
    returns = prices.pct_change().dropna()
    by_class = {k: [t for t in v if t in returns.columns] for k, v in CANDIDATES.items() if k != "sector"}
    return greedy_low_correlation(returns, by_class, n_total=13)


def plan_c_long_backtest(info_map: dict[str, ETFInfo], prices: pd.DataFrame) -> list[str]:
    """Plan C: ETFs with 15+ years of data."""
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=15 * 365)
    has_15y = []
    for t in prices.columns:
        first = prices[t].dropna().index.min()
        if first is not pd.NaT and first <= cutoff:
            has_15y.append(t)

    by_class = {k: [t for t in v if t in has_15y] for k, v in CANDIDATES.items() if k != "sector"}
    selected = []
    for cat, tickers in by_class.items():
        selected.extend(tickers[:3])
    selected = list(dict.fromkeys(selected))[:13]
    if len(selected) < 13:
        selected.extend([t for t in has_15y if t not in selected][: 13 - len(selected)])
    return selected[:13]


def plan_d_low_expense(info_map: dict[str, ETFInfo]) -> list[str]:
    """Plan D: Lowest expense ratio per category, prefer ER < 0.30%."""
    out = []
    for cat, tickers in CANDIDATES.items():
        if cat == "sector":
            continue
        valid = [
            (t, info_map[t])
            for t in tickers
            if t in info_map and info_map[t].passes_basic(max_er=0.5)
        ]
        valid.sort(key=lambda x: x[1].expense_ratio or 1)
        n = 3 if cat in ("us_equity", "bonds", "commodities") else 2 if cat == "intl_equity" else 1
        out.extend([t for t, _ in valid[:n]])
    # Fill to 13 if short (e.g. currency has only 1-2)
    if len(out) < 13:
        all_cands = [t for tickers in CANDIDATES.values() for t in tickers if t not in out and t in info_map]
        all_cands.sort(key=lambda t: info_map[t].expense_ratio or 1)
        out.extend(all_cands[: 13 - len(out)])
    return out[:13]


def plan_e_sector_tilt(info_map: dict[str, ETFInfo]) -> list[str]:
    """Plan E: 15 ETFs including sector ETFs."""
    base = ["SPY", "QQQ", "IWM", "IYR", "EFA", "EEM", "TLT", "IEF", "LQD", "TIP", "GLD", "USO", "DBC"]
    sector_cands = [t for t in CANDIDATES["sector"] if t in info_map and info_map[t].passes_basic()]
    sector_cands = sector_cands[:3]  # add up to 3 sectors
    return (base + sector_cands)[:15]


def run_all_plans() -> dict:
    """Run all 5 plans and return results."""
    print("Fetching ETF metadata...")
    info_map = fetch_all_info()
    all_tickers = list(info_map.keys())

    print("Fetching 20y price data...")
    prices = fetch_prices(all_tickers, 20)
    returns = prices.pct_change().dropna()

    # Update has_15y_data
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=15 * 365)
    for t in info_map:
        if t in prices.columns:
            first = prices[t].dropna().index.min()
            if first is not pd.NaT and first <= cutoff:
                info_map[t].has_15y_data = True
                info_map[t].first_date = str(first.date())

    results = {}

    print("Plan A: QuantPedia Classic...")
    results["A_QuantPedia_Classic"] = plan_a_quantpedia_classic(info_map)

    print("Plan B: Low Correlation...")
    results["B_Low_Correlation"] = plan_b_low_correlation(info_map, prices)

    print("Plan C: Long Backtest...")
    results["C_Long_Backtest"] = plan_c_long_backtest(info_map, prices)

    print("Plan D: Low Expense...")
    results["D_Low_Expense"] = plan_d_low_expense(info_map)

    print("Plan E: Sector Tilt...")
    results["E_Sector_Tilt"] = plan_e_sector_tilt(info_map)

    return {
        "info_map": {t: {"name": i.name, "aum_m": i.aum_m, "er": i.expense_ratio, "has_15y": i.has_15y_data} for t, i in info_map.items()},
        "plans": results,
        "run_time": datetime.now().isoformat(),
    }


def main() -> None:
    data = run_all_plans()

    # Write JSON (without numpy)
    def convert(obj):
        if isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    out_path = OUT_DIR / "plans_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in data.items() if k != "info_map"}, f, indent=2, default=convert)

    # Write readable markdown
    md_path = OUT_DIR / "plans_result.md"
    lines = [
        "# ETF Selection Results - 5 Plans",
        "",
        "| Plan | Focus | n ETFs | Key Difference |",
        "|------|-------|--------|-----------------|",
        "| A | QuantPedia Classic | 13 | โครงสร้างเดิม mainstream |",
        "| B | Low Correlation | 13 | minimize pairwise correlation |",
        "| C | Long Backtest | 13 | มี data 15+ ปี |",
        "| D | Low Expense | 13 | cost-efficient |",
        "| E | Sector Tilt | 15 | เพิ่ม sector ETFs (XLU, XLF) |",
        "",
        "---",
        "",
    ]
    for plan_name, etfs in data["plans"].items():
        lines.append(f"## {plan_name}")
        lines.append("")
        lines.append("| # | Ticker |")
        lines.append("|---|--------|")
        for i, t in enumerate(etfs, 1):
            lines.append(f"| {i} | {t} |")
        lines.append("")
        lines.append(f"**Total:** {len(etfs)} ETFs")
        lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # Write per-plan JSON for simulate.py
    plan_files = [
        ("A_QuantPedia_Classic", "plan_a_quantpedia.json", "QuantPedia Classic"),
        ("B_Low_Correlation", "plan_b_low_corr.json", "Low Correlation"),
        ("C_Long_Backtest", "plan_c_long_backtest.json", "Long Backtest"),
        ("D_Low_Expense", "plan_d_low_expense.json", "Low Expense"),
        ("E_Sector_Tilt", "plan_e_sector_tilt.json", "Sector Tilt"),
    ]
    for plan_key, fname, focus in plan_files:
        cfg = {"group_name": fname.replace(".json", ""), "etfs": data["plans"][plan_key], "focus": focus}
        with open(OUT_DIR / fname, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)

    print(f"\nResults written to {out_path}, {md_path}, and plan_*.json")


if __name__ == "__main__":
    main()
