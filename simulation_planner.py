"""
รัน dip_buy backtest หลายช่วงปีตาม planner.yaml (grid / grid-exit) แล้วเทียบและรวมผล
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import yaml


def _to_native(obj: Any) -> Any:
    """Convert numpy/scalar types to native Python for YAML dump."""
    if hasattr(obj, "item"):
        return obj.item()
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_native(x) for x in obj]
    if isinstance(obj, (np.integer, np.floating)):
        return int(obj) if isinstance(obj, np.integer) else float(obj)
    return obj

from etf_data_fetcher import ETFDataFetcher
from dip_buy_backtest import (
    DipBuyParams,
    ExitRules,
    load_dip_defaults,
    load_dip_sim_config,
    param_grid_reasonable,
    exit_rules_grid,
    small_grid_from_config,
    grid_search,
    grid_search_exit,
    summarize_best,
    summarize_by_group,
    summarize_all_exclude_commodity,
    _parse_start_date,
)


def _resolve_path(base_dir: Path, raw: Optional[str]) -> Optional[Path]:
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = base_dir / p
    return p if p.exists() else None


def load_planner(planner_path: Path) -> Dict[str, Any]:
    with open(planner_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def run_period(
    period: Dict[str, Any],
    fetcher: ETFDataFetcher,
    tickers: List[str],
    mode: str,
    default_params: DipBuyParams,
    exit_rules: ExitRules,
    param_list: List[DipBuyParams],
    exit_rules_list: List[ExitRules],
    history_calendar_days: int,
    max_workers: Optional[int] = None,
) -> List[Dict[str, Any]]:
    start_date = _parse_start_date(period.get("start_date"))
    end_date = _parse_start_date(period.get("end_date"))
    if mode == "grid_exit":
        return grid_search_exit(
            fetcher,
            tickers,
            default_params,
            exit_rules_list,
            history_calendar_days=history_calendar_days,
            sim_start_date=start_date,
            sim_end_date=end_date,
            max_workers=max_workers,
        )
    return grid_search(
        fetcher,
        tickers,
        param_list,
        exit_rules,
        history_calendar_days=history_calendar_days,
        sim_start_date=start_date,
        sim_end_date=end_date,
        max_workers=max_workers,
    )


def _append_yaml_doc(path: Path, data: Dict[str, Any]) -> None:
    """Append a YAML document (--- separated) so we can stream progress while long runs execute."""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = yaml.safe_dump(_to_native(data), allow_unicode=True, default_flow_style=False, sort_keys=False)
    with open(path, "a", encoding="utf-8") as f:
        # Separator between docs; makes it easy to tail/parse as YAML stream.
        f.write("---\n")
        f.write(doc)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run dip_buy per period from planner.yaml, compare & aggregate")
    parser.add_argument("--planner", type=str, default="planner.yaml", help="Path to planner.yaml")
    parser.add_argument("--limit", type=int, default=None, help="Override planner limit (tickers)")
    parser.add_argument(
        "--progress",
        type=str,
        default=None,
        help="Append per-period progress as YAML stream to this path (default: planner_progress.yaml next to planner)",
    )
    parser.add_argument("--workers", type=int, default=None, help="Max parallel processes per period (default: cpu_count)")
    args = parser.parse_args()

    planner_path = Path(args.planner)
    if not planner_path.is_absolute():
        planner_path = Path.cwd() / planner_path
    if not planner_path.exists():
        raise SystemExit(f"Planner not found: {planner_path}")

    base_dir = planner_path.resolve().parent
    plan = load_planner(planner_path)
    mode = (plan.get("mode") or "single").strip().lower()

    progress_path = Path(args.progress) if args.progress else (base_dir / "planner_progress.yaml")
    if mode not in ("single", "small_grid", "grid", "grid_exit"):
        mode = "single"

    dip_config_path = _resolve_path(base_dir, plan.get("dip_config"))
    sim_config_path = _resolve_path(base_dir, plan.get("sim_config"))
    default_params, exit_rules, _ = load_dip_defaults(dip_config_path)

    if mode == "grid_exit":
        exit_rules_list = exit_rules_grid(
            spread_pct=exit_rules.spread_pct,
            sim_config_path=sim_config_path,
        )
        param_list = [default_params]
    elif mode == "grid":
        param_list = param_grid_reasonable(sim_config_path)
    elif mode == "small_grid":
        param_list = small_grid_from_config(sim_config_path) or [
            DipBuyParams(100, 7, 20, True, 0.0),
            DipBuyParams(200, 7, 20, True, 0.0),
            DipBuyParams(200, 5, 20, False, 2.0),
        ]
    else:
        param_list = [default_params]
    if mode != "grid_exit":
        exit_rules_list = [exit_rules]

    fetcher = ETFDataFetcher()
    tickers = list(fetcher.tickers_map.keys())
    limit = args.limit if args.limit is not None else plan.get("limit")
    if limit is not None and isinstance(limit, int) and limit > 0:
        tickers = tickers[: limit]

    periods = plan.get("periods") or []
    if not periods:
        raise SystemExit("planner.yaml has no 'periods'")

    # ใช้ history ครอบทุกช่วง (อย่างน้อย 20 ปี)
    history_calendar_days = 20 * 365 + 60

    period_results: Dict[str, List[Dict[str, Any]]] = {}
    for period in periods:
        name = period.get("name") or period.get("start_date", "?")
        start_s = period.get("start_date")
        end_s = period.get("end_date")
        print(f"Running period: {name} ({start_s} .. {end_s}) ...")

        _append_yaml_doc(progress_path, {
            "event": "period_start",
            "period": {"name": name, "start_date": start_s, "end_date": end_s},
            "mode": mode,
            "limit": limit,
        })

        t0 = pd.Timestamp.utcnow()
        results = run_period(
            period,
            fetcher,
            tickers,
            mode,
            default_params,
            exit_rules,
            param_list,
            exit_rules_list,
            history_calendar_days,
            max_workers=args.workers,
        )
        dt_sec = float((pd.Timestamp.utcnow() - t0).total_seconds())

        period_results[name] = results
        print(f"  -> {len(results)} results")

        # Stream per-period summaries so you can inspect mid-run.
        try:
            best_overall = summarize_best(results, by_ticker=False, metric="total_return_pct")
            by_group = summarize_by_group(results, metric="total_return_pct")
            excl_commodity = summarize_all_exclude_commodity(results, metric="total_return_pct")
            _append_yaml_doc(progress_path, {
                "event": "period_done",
                "period": {"name": name, "start_date": start_s, "end_date": end_s},
                "runtime_sec": round(dt_sec, 3),
                "n_results": len(results),
                "best_overall": best_overall.to_dict(orient="records") if best_overall is not None and not best_overall.empty else [],
                "summary_by_group_top": by_group.head(15).to_dict(orient="records") if by_group is not None and not by_group.empty else [],
                "all_exclude_commodity": excl_commodity.to_dict(orient="records") if excl_commodity is not None and not excl_commodity.empty else [],
            })
        except Exception as e:
            _append_yaml_doc(progress_path, {
                "event": "period_done",
                "period": {"name": name, "start_date": start_s, "end_date": end_s},
                "runtime_sec": round(dt_sec, 3),
                "n_results": len(results),
                "error": str(e),
            })

    # เทียบ: best overall ต่อช่วง
    comparison_rows = []
    for period_name, results in period_results.items():
        if not results:
            comparison_rows.append({
                "period": period_name,
                "total_return_pct": None,
                "n_trades": None,
                "win_rate": None,
                "max_drawdown_pct": None,
            })
            continue
        best = summarize_best(results, by_ticker=False, metric="total_return_pct")
        if best.empty:
            comparison_rows.append({"period": period_name, "total_return_pct": None, "n_trades": None, "win_rate": None, "max_drawdown_pct": None})
            continue
        row = best.iloc[0]
        comparison_rows.append({
            "period": period_name,
            "total_return_pct": round(float(row["total_return_pct"]), 4),
            "n_trades": int(row["n_trades"]),
            "win_rate": round(float(row["win_rate"]), 2),
            "max_drawdown_pct": round(float(row["max_drawdown_pct"]), 2),
        })
    comparison_df = pd.DataFrame(comparison_rows)

    # รวม: ค่าเฉลี่ย return ตามช่วง (และสรุป exclude commodity ต่อช่วง ถ้าต้องการ)
    print("\n--- เทียบช่วง (best overall ต่อช่วง) ---")
    pd.set_option("display.width", 200)
    print(comparison_df.to_string(index=False))

    agg_return = comparison_df["total_return_pct"].dropna()
    if len(agg_return) > 0:
        print(f"\n--- รวม --- mean(total_return_pct) = {round(agg_return.mean(), 4)}%")

    # สรุป by group ต่อช่วง (ช่วงแรกเป็นตัวแทน)
    first_period_name = list(period_results.keys())[0] if period_results else None
    if first_period_name and period_results[first_period_name]:
        by_group = summarize_by_group(period_results[first_period_name], metric="total_return_pct")
        if not by_group.empty:
            print(f"\n--- สรุปต่อกลุ่ม (ช่วง {first_period_name}) ---")
            print(by_group.head(15).to_string())

    # บันทึก YAML
    output_path = plan.get("output")
    if output_path:
        out_path = base_dir / output_path if not Path(output_path).is_absolute() else Path(output_path)
        out_data = {
            "planner": str(planner_path),
            "mode": mode,
            "periods": [
                {
                    "name": p.get("name"),
                    "start_date": p.get("start_date"),
                    "end_date": p.get("end_date"),
                }
                for p in periods
            ],
            "comparison": comparison_df.to_dict(orient="records"),
            "aggregate_mean_return_pct": round(float(agg_return.mean()), 4) if len(agg_return) > 0 else None,
        }
        out_data = _to_native(out_data)
        with open(out_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(out_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
