#!/usr/bin/env python3
"""
CLI: fetch 20yr ETF data, run RSI/SMA grid search, output console + YAML + HTML charts.
Run from repo root (etf/) or from indicator-simulator/ (adds parent to path).
"""
from __future__ import annotations

import argparse
import itertools
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yaml

# Allow running from indicator-simulator/ with parent etf as project root
_SCRIPT_DIR = Path(__file__).resolve().parent
_ETF_ROOT = _SCRIPT_DIR.parent
if str(_ETF_ROOT) not in sys.path:
    sys.path.insert(0, str(_ETF_ROOT))

from core.etf_data_fetcher import ETFDataFetcher

# Import backtest engine from same package
sys.path.insert(0, str(_SCRIPT_DIR))
import indicator_backtest as ib

CONFIG_PATH = _SCRIPT_DIR / "sim_config.yaml"
RESULTS_DIR = _ETF_ROOT / "result"
YAML_OUT = RESULTS_DIR / "indicator_sim_result.yaml"
HTML_OUT = RESULTS_DIR / "indicator_sim_charts.html"

# 20 years + cushion (calendar days)
HISTORY_DAYS = 20 * 365 + 60


def _annualized_return_pct(total_return_pct: float, years: float) -> float:
    """CAGR: ((1 + total_return_pct/100)^(1/years) - 1) * 100. Returns 0 if years <= 0."""
    if not years or years <= 0:
        return 0.0
    if total_return_pct <= -100.0:
        return -100.0
    return float(((1.0 + total_return_pct / 100.0) ** (1.0 / years) - 1.0) * 100.0)


def _load_config(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _sma_param_grid(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    periods = config.get("strategies", {}).get("sma_crossover", {}).get("sma_period") or [20, 50, 100, 150, 200]
    return [{"sma_period": p} for p in periods]


def _rsi_param_grid(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    s = config.get("strategies", {}).get("rsi_mean_reversion") or {}
    r = s.get("rsi_period") or [7, 14, 21, 30]
    b = s.get("rsi_buy_threshold") or [25, 30, 35]
    e = s.get("rsi_sell_threshold") or [65, 70, 75]
    return [{"rsi_period": rp, "rsi_buy_threshold": bb, "rsi_sell_threshold": ee} for rp in r for bb in b for ee in e]


def _combined_param_grid(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    s = config.get("strategies", {}).get("combined_rsi_sma") or {}
    r = s.get("rsi_period") or [14, 21]
    b = s.get("rsi_buy_threshold") or [30, 35]
    e = s.get("rsi_sell_threshold") or [70, 75]
    sma = s.get("sma_period") or [50, 100, 200]
    return [
        {"rsi_period": rp, "rsi_buy_threshold": bb, "rsi_sell_threshold": ee, "sma_period": sp}
        for rp in r for bb in b for ee in e for sp in sma
    ]


def _run_one_backtest(
    ticker: str,
    df: pd.DataFrame,
    group_key: str,
    group_name: str,
    strategy: str,
    params: Dict[str, Any],
    initial_capital: float,
) -> Dict[str, Any]:
    """Single backtest for one ticker × strategy × params. Used in ProcessPoolExecutor."""
    df = df.sort_index()
    if strategy == "sma_crossover":
        signals = ib.generate_sma_signals(df, params["sma_period"])
    elif strategy == "rsi_mean_reversion":
        signals = ib.generate_rsi_signals(
            df,
            params["rsi_period"],
            params["rsi_buy_threshold"],
            params["rsi_sell_threshold"],
        )
    else:
        signals = ib.generate_combined_signals(
            df,
            params["rsi_period"],
            params["rsi_buy_threshold"],
            params["rsi_sell_threshold"],
            params["sma_period"],
        )
    metrics = ib.run_backtest(df, signals, initial_capital=initial_capital)
    return {
        "ticker": ticker,
        "group_key": group_key,
        "group_name": group_name,
        "strategy": strategy,
        "params": params,
        **metrics,
    }


def _run_one_backtest_star(args: Tuple) -> Dict[str, Any]:
    return _run_one_backtest(*args)


def run_grid_search(
    history: Dict[str, pd.DataFrame],
    ticker_infos: Dict[str, Dict],
    config: Dict[str, Any],
    strategies: List[str],
    workers: int,
) -> Dict[str, List[Dict[str, Any]]]:
    """Run grid search for selected strategies; return results by strategy name."""
    backtest_cfg = config.get("backtest") or {}
    initial_capital = float(backtest_cfg.get("initial_capital", 10000))

    out: Dict[str, List[Dict[str, Any]]] = {s: [] for s in strategies}

    for strategy in strategies:
        if strategy == "sma_crossover":
            param_list = _sma_param_grid(config)
        elif strategy == "rsi_mean_reversion":
            param_list = _rsi_param_grid(config)
        else:
            param_list = _combined_param_grid(config)

        tasks: List[Tuple] = []
        for ticker, df in history.items():
            if df is None or df.empty or "Close" not in df.columns:
                continue
            info = ticker_infos.get(ticker) or {}
            group_key = info.get("group_key") or "unknown"
            group_name = info.get("group") or group_key
            for params in param_list:
                tasks.append((ticker, df, group_key, group_name, strategy, params, initial_capital))

        if not tasks:
            continue

        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_run_one_backtest_star, t) for t in tasks]
            for future in as_completed(futures):
                try:
                    res = future.result()
                    out[strategy].append(res)
                except Exception:
                    pass

    return out


def _best_per_ticker(
    results: List[Dict],
    metric: str = "total_return_pct",
    min_trades: Optional[int] = None,
) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()
    rows = []
    for r in results:
        rows.append({
            "ticker": r["ticker"],
            "group_name": r.get("group_name", ""),
            "strategy": r["strategy"],
            "params": r["params"],
            "total_return_pct": r[metric],
            "n_trades": r["n_trades"],
            "win_rate": r["win_rate"],
            "max_drawdown_pct": r["max_drawdown_pct"],
        })
    df = pd.DataFrame(rows)
    if min_trades is not None and min_trades > 0:
        df = df[df["n_trades"] >= min_trades]
    if df.empty:
        return pd.DataFrame()
    idx = df.groupby("ticker")[metric].idxmax()
    return df.loc[idx].sort_values(metric, ascending=False).reset_index(drop=True)


def _best_per_group(
    results: List[Dict],
    metric: str = "total_return_pct",
    min_trades: Optional[int] = None,
) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()
    rows = []
    for r in results:
        row = {"group_name": r.get("group_name", ""), "group_key": r.get("group_key", ""), "ticker": r["ticker"], metric: r[metric], "win_rate": r["win_rate"], "max_drawdown_pct": r["max_drawdown_pct"], "n_trades": r["n_trades"]}
        row.update(r["params"])
        rows.append(row)
    df = pd.DataFrame(rows)
    if min_trades is not None and min_trades > 0:
        df = df[df["n_trades"] >= min_trades]
    if df.empty:
        return pd.DataFrame()
    param_cols = [c for c in df.columns if c not in ["group_name", "group_key", "ticker", metric, "win_rate", "max_drawdown_pct", "n_trades"]]
    best_rows = []
    for group_name, g in df.groupby("group_name"):
        n_tickers = g["ticker"].nunique()
        if not param_cols:
            best_rows.append({"group_name": group_name, "n_tickers": n_tickers, "mean_return_pct": g[metric].mean(), "mean_win_rate": g["win_rate"].mean(), "mean_max_dd_pct": g["max_drawdown_pct"].mean()})
            continue
        by_params = g.groupby(param_cols, dropna=False)[metric].mean().reset_index()
        best_idx = by_params[metric].idxmax()
        best_row = by_params.loc[best_idx]
        mask = pd.Series(True, index=g.index)
        for c in param_cols:
            if c not in g.columns:
                continue
            match = g[c] == best_row[c]
            mask = mask & match
        sub = g.loc[mask]
        rec = {"group_name": group_name, "n_tickers": n_tickers, "mean_return_pct": round(best_row[metric], 4), "mean_win_rate": round(sub["win_rate"].mean(), 2), "mean_max_dd_pct": round(sub["max_drawdown_pct"].mean(), 2)}
        rec.update({c: best_row[c] for c in param_cols})
        best_rows.append(rec)
    return pd.DataFrame(best_rows).sort_values("mean_return_pct", ascending=False).reset_index(drop=True)


def _best_overall(
    results: List[Dict],
    metric: str = "total_return_pct",
    min_trades: Optional[int] = None,
) -> Dict[str, Any]:
    if not results:
        return {}
    df = pd.DataFrame([{**r["params"], metric: r[metric], "win_rate": r["win_rate"], "max_drawdown_pct": r["max_drawdown_pct"], "n_trades": r["n_trades"]} for r in results])
    if min_trades is not None and min_trades > 0:
        df = df[df["n_trades"] >= min_trades]
    if df.empty:
        return {}
    param_cols = [c for c in df.columns if c not in [metric, "win_rate", "max_drawdown_pct", "n_trades"]]
    if not param_cols:
        best = df.loc[df[metric].idxmax()].iloc[0]
        return best.to_dict()
    by_params = df.groupby(param_cols, dropna=False)[metric].mean()
    best_params_idx = by_params.idxmax()
    if isinstance(best_params_idx, (list, tuple)):
        best_combo = dict(zip(param_cols, list(best_params_idx)))
    else:
        best_combo = {param_cols[0]: best_params_idx}
    sub = df.copy()
    for c, v in best_combo.items():
        if c in sub.columns:
            sub = sub[sub[c] == v]
    if sub.empty:
        return {**best_combo, "mean_return_pct": float(by_params.max()), "mean_win_rate": 0.0, "mean_max_dd_pct": 0.0, "n_trades": 0}
    row = sub.iloc[0]
    return {**best_combo, "mean_return_pct": float(by_params.max()), "mean_win_rate": float(row["win_rate"]), "mean_max_dd_pct": float(row["max_drawdown_pct"]), "n_trades": int(row["n_trades"])}


def _params_str(strategy: str, params: Dict) -> str:
    if strategy == "sma_crossover":
        return str(params.get("sma_period", ""))
    if strategy == "rsi_mean_reversion":
        return f"{params.get('rsi_period')}/{params.get('rsi_buy_threshold')}/{params.get('rsi_sell_threshold')}"
    return f"{params.get('rsi_period')}/{params.get('rsi_buy_threshold')}/{params.get('rsi_sell_threshold')}/sma{params.get('sma_period')}"


def _print_console(results_by_strategy: Dict[str, List[Dict]], config: Dict[str, Any]) -> None:
    backtest_cfg = config.get("backtest") or {}
    years = backtest_cfg.get("years", 20)
    min_trades = backtest_cfg.get("min_trades_for_best")

    for strategy, results in results_by_strategy.items():
        if not results:
            continue
        by_group = _best_per_group(results, min_trades=min_trades)
        by_ticker = _best_per_ticker(results, min_trades=min_trades)
        overall = _best_overall(results, min_trades=min_trades)
        by_group = by_group.copy()
        by_group["annualized_return_pct"] = by_group["mean_return_pct"].apply(lambda r: _annualized_return_pct(r, years))

        if strategy == "sma_crossover":
            print("\n--- SMA Crossover: Best per group ---")
            print(f"{'group_name':<28} | {'best_sma':<8} | {'mean_return%':<12} | {'ann%':<8} | {'win_rate':<8} | {'max_dd%':<8} | {'n_tickers':<8}")
            for _, row in by_group.iterrows():
                sma = row.get("sma_period", "")
                print(f"{str(row['group_name']):<28} | {sma!s:<8} | {row['mean_return_pct']:<12.2f} | {row['annualized_return_pct']:<8.2f} | {row['mean_win_rate']:<8.2f} | {row['mean_max_dd_pct']:<8.2f} | {row['n_tickers']:<8}")
        elif strategy == "rsi_mean_reversion":
            print("\n--- RSI Mean-Reversion: Best per group ---")
            print(f"{'group_name':<28} | {'rsi_p':<6} | {'buy_th':<6} | {'sell_th':<6} | {'mean_return%':<12} | {'ann%':<8} | {'win_rate':<8} | {'n_tickers':<8}")
            for _, row in by_group.iterrows():
                print(f"{str(row['group_name']):<28} | {row.get('rsi_period',''):<6} | {row.get('rsi_buy_threshold',''):<6} | {row.get('rsi_sell_threshold',''):<6} | {row['mean_return_pct']:<12.2f} | {row['annualized_return_pct']:<8.2f} | {row['mean_win_rate']:<8.2f} | {row['n_tickers']:<8}")
        else:
            print("\n--- Combined RSI+SMA: Best per group ---")
            print(f"{'group_name':<28} | {'params':<20} | {'mean_return%':<12} | {'ann%':<8} | {'win_rate':<8} | {'n_tickers':<8}")
            for _, row in by_group.iterrows():
                params_str = _params_str(strategy, row)
                print(f"{str(row['group_name']):<28} | {params_str:<20} | {row['mean_return_pct']:<12.2f} | {row['annualized_return_pct']:<8.2f} | {row['mean_win_rate']:<8.2f} | {row['n_tickers']:<8}")

    print("\n--- Per-ticker detail (top 20) ---")
    all_ticker = []
    for strategy, results in results_by_strategy.items():
        bt = _best_per_ticker(results, min_trades=min_trades)
        bt = bt.copy()
        bt["annualized_return_pct"] = bt["total_return_pct"].apply(lambda r: _annualized_return_pct(r, years))
        for r in bt.to_dict("records"):
            r["_strategy"] = strategy
            all_ticker.append(r)
    if all_ticker:
        all_df = pd.DataFrame(all_ticker)
        all_df = all_df.sort_values("total_return_pct", ascending=False).head(20)
        print(f"{'ticker':<8} | {'strategy':<10} | {'params':<22} | {'return%':<10} | {'ann%':<8} | {'trades':<6} | {'win_rate':<8} | {'max_dd%':<8}")
        for _, row in all_df.iterrows():
            params_str = _params_str(row["_strategy"], row.get("params") or {})
            ann = _annualized_return_pct(row["total_return_pct"], years)
            print(f"{row['ticker']:<8} | {row['_strategy']:<10} | {params_str:<22} | {row['total_return_pct']:<10.2f} | {ann:<8.2f} | {row['n_trades']:<6} | {row['win_rate']:<8.2f} | {row['max_drawdown_pct']:<8.2f}")


def _build_yaml_payload(
    run_meta: Dict[str, Any],
    results_by_strategy: Dict[str, List[Dict]],
) -> Dict[str, Any]:
    years = run_meta.get("years", 20)
    min_trades = run_meta.get("min_trades_for_best")

    def _to_yaml_friendly(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _to_yaml_friendly(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_to_yaml_friendly(x) for x in obj]
        if hasattr(obj, "item"):
            return obj.item()
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat() if hasattr(obj, "isoformat") else str(obj)
        if isinstance(obj, float) and (obj != obj):
            return None
        return obj

    strategies_out = {}
    for name, results in results_by_strategy.items():
        if not results:
            continue
        by_ticker = _best_per_ticker(results, min_trades=min_trades)
        by_group = _best_per_group(results, min_trades=min_trades)
        overall = _best_overall(results, min_trades=min_trades)
        by_ticker = by_ticker.copy()
        by_ticker["annualized_return_pct"] = by_ticker["total_return_pct"].apply(lambda r: _annualized_return_pct(r, years))
        by_group = by_group.copy()
        by_group["annualized_return_pct"] = by_group["mean_return_pct"].apply(lambda r: _annualized_return_pct(r, years))
        overall = dict(overall)
        overall["annualized_return_pct"] = _annualized_return_pct(overall.get("mean_return_pct", 0.0), years)
        strategies_out[name] = {
            "best_overall": _to_yaml_friendly(overall),
            "by_group": _to_yaml_friendly(by_group.to_dict("records") if not by_group.empty else []),
            "by_ticker": _to_yaml_friendly(by_ticker.to_dict("records") if not by_ticker.empty else []),
        }
    return {
        "run": _to_yaml_friendly(run_meta),
        "strategies": strategies_out,
    }


def _write_html_charts(
    results_by_strategy: Dict[str, List[Dict]],
    history: Dict[str, pd.DataFrame],
    output_path: Path,
    years: float = 20,
    min_trades: Optional[int] = None,
) -> None:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        return

    figs = []

    # 1) SMA heatmap: group x sma_period -> mean return
    if results_by_strategy.get("sma_crossover"):
        res = results_by_strategy["sma_crossover"]
        df = pd.DataFrame([{**r["params"], "group_name": r.get("group_name", ""), "total_return_pct": r["total_return_pct"]} for r in res])
        if not df.empty and "sma_period" in df.columns:
            pivot = df.pivot_table(values="total_return_pct", index="group_name", columns="sma_period", aggfunc="mean")
            fig = go.Figure(data=go.Heatmap(
                z=pivot.values.tolist(),
                x=[str(x) for x in pivot.columns.tolist()],
                y=pivot.index.tolist(),
                colorscale="RdYlGn",
            ))
            fig.update_layout(title="SMA period vs group (mean return %)", xaxis_title="SMA period", yaxis_title="Group")
            figs.append(fig)

    # 2) RSI heatmap: buy_th vs sell_th buy_th vs sell_th per group (one group or aggregate)
    if results_by_strategy.get("rsi_mean_reversion"):
        res = results_by_strategy["rsi_mean_reversion"]
        df = pd.DataFrame([{**r["params"], "group_name": r.get("group_name", ""), "total_return_pct": r["total_return_pct"]} for r in res])
        if not df.empty and "rsi_buy_threshold" in df.columns and "rsi_sell_threshold" in df.columns:
            pivot = df.pivot_table(values="total_return_pct", index="rsi_buy_threshold", columns="rsi_sell_threshold", aggfunc="mean")
            fig = go.Figure(data=go.Heatmap(
                z=pivot.values.tolist(),
                x=[str(x) for x in pivot.columns.tolist()],
                y=[str(y) for y in pivot.index.tolist()],
                colorscale="RdYlGn",
            ))
            fig.update_layout(title="RSI buy vs sell threshold (mean return %)", xaxis_title="Sell threshold", yaxis_title="Buy threshold")
            figs.append(fig)

    # 3) Bar: best strategy comparison per group (with annualized return)
    group_best: Dict[str, Dict[str, Any]] = {}
    for strategy, results in results_by_strategy.items():
        by_group = _best_per_group(results, min_trades=min_trades)
        for _, row in by_group.iterrows():
            gn = str(row["group_name"])
            ann = _annualized_return_pct(row["mean_return_pct"], years)
            if gn not in group_best or row["mean_return_pct"] > group_best[gn].get("return", -1e9):
                group_best[gn] = {"return": row["mean_return_pct"], "annualized": ann, "strategy": strategy}
    if group_best:
        groups = list(group_best.keys())
        returns = [group_best[g]["return"] for g in groups]
        annualized = [group_best[g]["annualized"] for g in groups]
        strategies = [group_best[g]["strategy"] for g in groups]
        fig = go.Figure(data=[
            go.Bar(
                x=groups,
                y=[float(r) for r in returns],
                text=[f"{r:.1f}%<br>({a:.1f}% ann)" for r, a in zip(returns, annualized)],
                textposition="outside",
                customdata=[[a, s] for a, s in zip(annualized, strategies)],
                hovertemplate="%{x}<br>Total: %{y:.2f}%<br>Annualized: %{customdata[0]:.2f}%<br>Strategy: %{customdata[1]}<extra></extra>",
            ),
        ])
        fig.update_layout(title="Best mean return % by group (with annualized %)", xaxis_title="Group", yaxis_title="Mean return %")
        figs.append(fig)

    # 4) Equity curves for top 5 tickers per strategy
    for strategy, results in results_by_strategy.items():
        by_ticker = _best_per_ticker(results, min_trades=min_trades)
        if by_ticker.empty:
            continue
        top5 = by_ticker.head(5)
        fig = go.Figure()
        for _, row in top5.iterrows():
            ticker = row["ticker"]
            if ticker not in history:
                continue
            df = history[ticker].sort_index()
            params = row.get("params") or {}
            if strategy == "sma_crossover":
                signals = ib.generate_sma_signals(df, params.get("sma_period", 50))
            elif strategy == "rsi_mean_reversion":
                signals = ib.generate_rsi_signals(df, params.get("rsi_period", 14), params.get("rsi_buy_threshold", 30), params.get("rsi_sell_threshold", 70))
            else:
                signals = ib.generate_combined_signals(df, params.get("rsi_period", 14), params.get("rsi_buy_threshold", 30), params.get("rsi_sell_threshold", 70), params.get("sma_period", 100))
            metrics = ib.run_backtest(df, signals)
            trades = metrics.get("trades_list") or []
            if not trades:
                continue
            eq = 1.0
            eq_dates = [df.index[0]]
            eq_vals = [1.0]
            for t in trades:
                eq *= 1.0 + t["return_pct"] / 100.0
                eq_dates.append(t["exit_date"])
                eq_vals.append(eq)
            fig.add_trace(go.Scatter(x=[d.isoformat() if hasattr(d, "isoformat") else str(d) for d in eq_dates], y=[float(v) for v in eq_vals], mode="lines", name=ticker))
        fig.update_layout(title=f"Equity curves (top 5 tickers) - {strategy}", xaxis_title="Date", yaxis_title="Cumulative return")
        figs.append(fig)

    if not figs:
        return
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("<!DOCTYPE html><html><head><meta charset='utf-8'/></head><body>\n")
        # Summary table: best per group with total and annualized return
        if group_best:
            f.write("<h3>Best per group (total return % / annualized return %)</h3>\n<table border='1' cellpadding='4'><tr><th>Group</th><th>Strategy</th><th>Total return %</th><th>Annualized %</th></tr>\n")
            for g in groups:
                r = group_best[g]["return"]
                a = group_best[g]["annualized"]
                s = group_best[g]["strategy"]
                f.write(f"<tr><td>{g}</td><td>{s}</td><td>{r:.2f}</td><td>{a:.2f}</td></tr>\n")
            f.write("</table><br>\n")
        for i, fig in enumerate(figs):
            f.write(fig.to_html(full_html=False, include_plotlyjs=(i == 0)))
        f.write("</body></html>\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Indicator simulator: RSI/SMA grid search on ETFs")
    parser.add_argument("--strategy", choices=["sma", "rsi", "combined", "all"], default="all", help="Strategy to run (default: all)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tickers (for testing)")
    parser.add_argument("--workers", type=int, default=None, help="Parallel workers (default: cpu_count)")
    parser.add_argument("--output-yaml", type=str, default=None, help="Output YAML path (default: results/indicator_sim_result.yaml)")
    parser.add_argument("--output-html", type=str, default=None, help="Output HTML charts path")
    args = parser.parse_args()

    config = _load_config(CONFIG_PATH)
    backtest_cfg = config.get("backtest") or {}
    years = backtest_cfg.get("years", 20)

    fetcher = ETFDataFetcher(yaml_path=str(_ETF_ROOT / "config" / "etf.yaml"), cache_dir=str(_ETF_ROOT / "cache"))
    tickers = list(fetcher.tickers_map.keys())
    if args.limit:
        tickers = tickers[: args.limit]

    calendar_days = years * 365 + 60
    history, errors = fetcher.fetch_history_days(int(calendar_days), tickers=tickers)
    if errors:
        print(f"Fetch errors ({len(errors)}):", list(errors.keys())[:5], "..." if len(errors) > 5 else "")

    ticker_infos = {}
    for t in tickers:
        info = fetcher.get_ticker_info(t) or {}
        ticker_infos[t] = {"group_key": info.get("group_key"), "group": info.get("group")}

    strategy_map = {"sma": "sma_crossover", "rsi": "rsi_mean_reversion", "combined": "combined_rsi_sma"}
    if args.strategy == "all":
        strategies = list(strategy_map.values())
    else:
        strategies = [strategy_map[args.strategy]]

    workers = args.workers or (os.cpu_count() or 4)
    results_by_strategy = run_grid_search(history, ticker_infos, config, strategies, workers)

    _print_console(results_by_strategy, config)

    run_meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "years": years,
        "n_tickers": len(tickers),
        "strategies": strategies,
        "min_trades_for_best": backtest_cfg.get("min_trades_for_best"),
    }
    yaml_path = Path(args.output_yaml) if args.output_yaml else YAML_OUT
    if not yaml_path.is_absolute():
        yaml_path = RESULTS_DIR / yaml_path.name
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _build_yaml_payload(run_meta, results_by_strategy)
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(payload, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"\n--- Result YAML: {yaml_path} ---")

    html_path = Path(args.output_html) if args.output_html else HTML_OUT
    if not html_path.is_absolute():
        html_path = RESULTS_DIR / html_path.name
    _write_html_charts(results_by_strategy, history, html_path, years=years, min_trades=backtest_cfg.get("min_trades_for_best"))
    print(f"--- Charts HTML: {html_path} ---")


if __name__ == "__main__":
    main()
