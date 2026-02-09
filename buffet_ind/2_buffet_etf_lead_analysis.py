"""
Analyze whether Buffett indicator leads ETF returns.
Uses data/buffet-ind.csv (annual) and data/etf_price_by_country.csv (daily).
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

DATA_DIR = Path(__file__).resolve().parent.parent / "data"  # Go up from buffet_ind/ to root
BUFFET_CSV = DATA_DIR / "buffet-ind.csv"
ETFA_CSV = DATA_DIR / "etf_price_by_country.csv"


def load_buffet() -> pd.DataFrame:
    """Load Buffett indicator: long form (country, year, value)."""
    df = pd.read_csv(BUFFET_CSV)
    year_cols = [c for c in df.columns if c.isdigit()]
    out = df[["country_code"]].copy()
    out = out.assign(
        **{y: pd.to_numeric(df[y], errors="coerce") for y in year_cols}
    )
    out = out.set_index("country_code").stack().reset_index()
    out.columns = ["country_code", "year", "buffet"]
    out["year"] = out["year"].astype(int)
    return out


def load_etf_annual() -> pd.DataFrame:
    """Load ETF prices and compute year-end price and next-year return per country."""
    df = pd.read_csv(ETFA_CSV)
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    df["year"] = df["Date"].dt.year
    # Last trading day per year per country
    cols = [c for c in df.columns if c not in ("Date", "year")]
    rows = []
    for year, g in df.groupby("year"):
        # use last available date in that year
        last = g.sort_values("Date").iloc[-1]
        for cc in cols:
            val = last.get(cc)
            if pd.api.types.is_number(val) and pd.notna(val):
                rows.append({"year": year, "country_code": cc, "etf_price": float(val)})
    price_df = pd.DataFrame(rows)
    price_df = price_df.sort_values(["country_code", "year"])
    price_df["etf_return_next"] = (
        price_df.groupby("country_code")["etf_price"].pct_change().shift(-1)
    )
    return price_df


def plot_pooled_scatter(merged: pd.DataFrame, b: np.ndarray, r: float, p: float, out_dir: Path) -> None:
    """Scatter: Buffett vs next-year ETF return with regression line."""
    fig, ax = plt.subplots(figsize=(8, 5))
    x = merged["buffet"].to_numpy()
    y = merged["etf_return_next"].to_numpy()
    ax.scatter(x, y, alpha=0.5, s=24, c="steelblue", edgecolors="none")
    xline = np.linspace(x.min(), x.max(), 100)
    ax.plot(xline, b[0] + b[1] * xline, color="crimson", lw=2, label="Regression")
    ax.axhline(0, color="gray", ls="--", alpha=0.7)
    ax.set_xlabel("Buffett indicator")
    ax.set_ylabel("Next-year ETF return")
    ax.set_title(f"Buffett vs next-year ETF return (pooled)\nr = {r:.3f}, p = {p:.3f}")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "buffet_etf_lead_pooled_scatter.png", dpi=120)
    plt.close(fig)


def plot_correlation_bars(corr_df: pd.DataFrame, out_dir: Path) -> None:
    """Bar chart of per-country correlation (sorted)."""
    df = corr_df.sort_values("corr")
    fig, ax = plt.subplots(figsize=(9, 6))
    colors = ["#2ecc71" if p < 0.05 else "#95a5a6" for p in df["p"]]
    bars = ax.barh(df["country_code"].tolist(), df["corr"].tolist(), color=colors)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("Correlation (Buffett vs next-year ETF return)")
    ax.set_title("Per-country correlation (green = p < 0.05)")
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "buffet_etf_lead_corr_bars.png", dpi=120)
    plt.close(fig)


def plot_country_examples(merged: pd.DataFrame, corr_df: pd.DataFrame, out_dir: Path) -> None:
    """Time series: Buffett and next-year return for a few countries."""
    # Pick 2 negative (significant) and 1 weak
    sig = corr_df[corr_df["p"] < 0.05].sort_values("corr").head(2)
    weak = corr_df[corr_df["p"] >= 0.05].sort_values("corr", ascending=False).head(1)
    picks = list(sig["country_code"]) + list(weak["country_code"])
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, cc in zip(axes, picks):
        g = merged[merged["country_code"] == cc].sort_values("year")
        row = corr_df[corr_df["country_code"] == cc].iloc[0]
        ax.bar(g["year"].tolist(), g["buffet"].tolist(), alpha=0.6, label="Buffett", color="steelblue")
        ax2 = ax.twinx()
        ax2.plot(g["year"].tolist(), g["etf_return_next"].tolist(), color="crimson", marker="o", ms=4, label="Next-yr return")
        ax.set_ylabel("Buffett indicator", color="steelblue")
        ax2.set_ylabel("Next-year return", color="crimson")
        ax.set_title(f"{cc} (r={row['corr']:.2f}, p={row['p']:.2f})")
        ax.legend(loc="upper left", fontsize=8)
        ax2.legend(loc="upper right", fontsize=8)
        ax.grid(True, alpha=0.3)
    fig.suptitle("Buffett indicator (bar) vs next-year ETF return (line) by country")
    fig.tight_layout()
    fig.savefig(out_dir / "buffet_etf_lead_country_examples.png", dpi=120)
    plt.close(fig)


def main() -> None:
    buffet = load_buffet()
    etf_annual = load_etf_annual()
    common_cc = set(buffet["country_code"]) & set(etf_annual["country_code"])
    buffet = buffet[buffet["country_code"].isin(common_cc)]
    etf_annual = etf_annual[etf_annual["country_code"].isin(common_cc)]

    merged = etf_annual.merge(
        buffet,
        on=["country_code", "year"],
        how="inner",
    ).dropna(subset=["buffet", "etf_return_next"])

    if merged.empty:
        print("No overlapping (country, year) with both Buffett and next-year ETF return.")
        return

    print("Buffett indicator vs next-year ETF return (leading indicator analysis)\n")
    print("Pooled (all countries, all years):")
    r, p = stats.pearsonr(merged["buffet"], merged["etf_return_next"])
    print(f"  Correlation(buffet, etf_return_next): r = {r:.4f}, p = {p:.4f}")

    # OLS: etf_return_next = a + b * buffet
    x = merged["buffet"].values
    y = merged["etf_return_next"].values
    x1 = np.column_stack([np.ones_like(x), x])
    b, _, _, _ = np.linalg.lstsq(x1, y, rcond=None)
    pred = x1 @ b
    res = y - pred
    n, k = x1.shape
    se = np.sqrt(np.sum(res**2) / (n - k))
    var_b = se**2 * np.linalg.inv(x1.T @ x1)
    se_b = np.sqrt(np.diag(var_b))
    t = b / se_b
    pval = 2 * (1 - stats.t.cdf(np.abs(t), n - k))
    print(f"  Regression: etf_return_next = {b[0]:.4f} + {b[1]:.4f} * buffet")
    print(f"  Slope se = {se_b[1]:.4f}, t = {t[1]:.4f}, p = {pval[1]:.4f}")

    print("\nPer-country correlation (buffet vs etf_return_next):")
    by_cc = merged.groupby("country_code")
    corrs = []
    for cc, g in by_cc:
        if len(g) < 4:
            continue
        r, p = stats.pearsonr(g["buffet"], g["etf_return_next"])
        corrs.append({"country_code": cc, "corr": r, "p": p, "n": len(g)})
    corr_df = pd.DataFrame(corrs).sort_values("corr", ascending=False)
    for _, row in corr_df.iterrows():
        sig = "*" if row["p"] < 0.05 else ""
        print(f"  {row['country_code']}: r = {row['corr']:.3f}, p = {row['p']:.3f}, n = {int(row['n'])} {sig}")

    result_dir = Path(__file__).resolve().parent.parent / "result"  # Go up from buffet_ind/ to root
    result_dir.mkdir(parents=True, exist_ok=True)
    corr_df.to_csv(result_dir / "buffet_etf_lead_corr.csv", index=False)
    print(f"\nPer-country correlations saved to {result_dir / 'buffet_etf_lead_corr.csv'}")

    # Visualizations
    plot_pooled_scatter(merged, b, r, p, result_dir)
    plot_correlation_bars(corr_df, result_dir)
    plot_country_examples(merged, corr_df, result_dir)
    print(f"Charts saved to {result_dir}: buffet_etf_lead_pooled_scatter.png, buffet_etf_lead_corr_bars.png, buffet_etf_lead_country_examples.png")


if __name__ == "__main__":
    main()
