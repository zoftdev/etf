#!/usr/bin/env python3
"""
Batch research runner — run hundreds/thousands of config variants in parallel.

Reads batch config from JSON file, runs each via ProcessPoolExecutor,
aggregates results, writes CSV/MD/HTML.

Usage:
  uv run python momentum-lab/run_batch.py batch.json [--name my-batch] [--workers 4]

Output: result/momentum-lab/_batch/{batch_name}/
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

# Add momentum-lab to path
_lab_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_lab_dir))

OUT_DIR = Path(__file__).resolve().parent.parent / "result" / "momentum-lab"
BATCH_BASE = OUT_DIR / "_batch"


def _run_one(config_dict: dict) -> dict:
    """Worker: run simulation for one config, return summary dict. Must be top-level for pickling."""
    from simulate import Config, default_config, run_simulation

    defaults = asdict(default_config())
    overrides = {k: v for k, v in config_dict.items() if v is not None}
    merged = {**defaults, **overrides}
    if "mom_periods_days" in merged and isinstance(merged["mom_periods_days"], list):
        merged["mom_periods_days"] = tuple(merged["mom_periods_days"])
    config = Config(**merged)

    result = run_simulation(config=config)
    return result.to_summary_dict()


def load_batch(path: Path) -> list[dict]:
    """Load batch configs from JSON file. Each element is a config override dict."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "configs" in data:
        configs = data["configs"]
    elif isinstance(data, list):
        configs = data
    else:
        raise ValueError("Batch file must be JSON array or {configs: [...]}")
    return configs


def flatten_summary(s: dict) -> dict:
    """Flatten nested summary for CSV row."""
    cfg = s.get("config", {})
    m0 = s.get("momentum_spread0", {})
    m15 = s.get("momentum_spread", {})
    bh = s.get("benchmark", {})
    dr = s.get("data_range", {})

    row = {
        "group_name": cfg.get("group_name", ""),
        "etfs": ",".join(cfg.get("etfs", [])),
        "n_long": cfg.get("n_long"),
        "n_short": cfg.get("n_short"),
        "spread_pct": cfg.get("spread_pct"),
        "mom0_cagr": m0.get("cagr_pct"),
        "mom0_sharpe": m0.get("sharpe"),
        "mom0_maxdd": m0.get("max_drawdown_pct"),
        "mom_cagr": m15.get("cagr_pct"),
        "mom_sharpe": m15.get("sharpe"),
        "mom_maxdd": m15.get("max_drawdown_pct"),
        "bh_cagr": bh.get("cagr_pct"),
        "bh_sharpe": bh.get("sharpe"),
        "bh_maxdd": bh.get("max_drawdown_pct"),
        "days": dr.get("days"),
    }
    return row


def write_csv(results: list[dict], out: Path) -> None:
    import csv

    if not results:
        return
    rows = [flatten_summary(r) for r in results]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)


def write_md(results: list[dict], out: Path) -> None:
    rows = [flatten_summary(r) for r in results]
    rows_sorted = sorted(rows, key=lambda x: (x.get("mom0_sharpe") or 0), reverse=True)

    lines = [
        "# Batch Research Results",
        "",
        f"Total runs: {len(results)}",
        "",
        "## Top 20 by Momentum Sharpe (spread=0)",
        "",
        "| group_name | n_long | mom0_cagr | mom0_sharpe | mom0_maxdd | bh_cagr | bh_sharpe |",
        "|------------|--------|-----------|-------------|------------|---------|-----------|",
    ]
    for r in rows_sorted[:20]:
        lines.append(
            f"| {r.get('group_name','')} | {r.get('n_long','')} | "
            f"{r.get('mom0_cagr',0):.2f}% | {r.get('mom0_sharpe',0):.2f} | {r.get('mom0_maxdd',0):.2f}% | "
            f"{r.get('bh_cagr',0):.2f}% | {r.get('bh_sharpe',0):.2f} |"
        )
    lines.extend(["", "## Full Table", ""])
    ncols = len(rows[0])
    lines.append("| " + " | ".join(rows[0].keys()) + " |")
    lines.append("|" + " --- |" * ncols)
    for r in rows_sorted:
        vals = [str(v) if v is not None else "" for v in r.values()]
        lines.append("| " + " | ".join(vals) + " |")

    out.write_text("\n".join(lines), encoding="utf-8")


def write_html(results: list[dict], out: Path) -> None:
    rows = [flatten_summary(r) for r in results]
    rows_sorted = sorted(rows, key=lambda x: (x.get("mom0_sharpe") or 0), reverse=True)

    thead = "".join(f"<th>{k}</th>" for k in rows[0].keys())
    tbody_rows = []
    for r in rows_sorted:
        tbody_rows.append(
            "<tr>" + "".join(f"<td>{v}</td>" for v in r.values()) + "</tr>"
        )
    tbody = "\n".join(tbody_rows)

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Batch Results</title>
<style>
  body {{ font-family: system-ui; margin: 2rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  th {{ background: #333; color: white; }}
  tr:nth-child(even) {{ background: #f9f9f9; }}
</style>
</head>
<body>
<h1>Batch Research Results</h1>
<p>Total runs: {len(results)}</p>
<table>
<thead><tr>{thead}</tr></thead>
<tbody>
{tbody}
</tbody>
</table>
</body>
</html>"""
    out.write_text(html, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch momentum strategy research")
    parser.add_argument("batch_file", type=Path, help="JSON file with config array")
    parser.add_argument("--name", type=str, default="",
                        help="Batch name (default: from filename)")
    parser.add_argument("--workers", type=int, default=14,
                        help="ProcessPoolExecutor workers")
    args = parser.parse_args()

    batch_name = args.name or args.batch_file.stem
    out_dir = BATCH_BASE / batch_name
    out_dir.mkdir(parents=True, exist_ok=True)

    configs = load_batch(args.batch_file)
    print(f"Loaded {len(configs)} configs from {args.batch_file}")

    results: list[dict] = []
    errors: list[tuple[int, str]] = []

    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(_run_one, c): i for i, c in enumerate(configs)}
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                r = fut.result()
                results.append(r)
                g = r.get("config", {}).get("group_name", i)
                print(f"  [{len(results)}/{len(configs)}] {g}")
            except Exception as e:
                errors.append((i, str(e)))
                print(f"  ERROR [{i}]: {e}")

    print(f"\nDone: {len(results)} ok, {len(errors)} errors")

    # Save configs for reference
    (out_dir / "configs.json").write_text(
        json.dumps(configs, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_csv(results, out_dir / "results.csv")
    write_md(results, out_dir / "report.md")
    write_html(results, out_dir / "report.html")

    if errors:
        (out_dir / "errors.json").write_text(
            json.dumps([{"index": i, "error": e} for i, e in errors], indent=2),
            encoding="utf-8",
        )

    print(f"Saved to {out_dir}/")
    print(f"  results.csv, results.json, report.md, report.html")


if __name__ == "__main__":
    main()
