#!/usr/bin/env python3
"""
Run batch optimize for each of 5 plan groups separately.
Then aggregate into a single report.

Steps:
  1. gen_batch_per_group.py → creates loop1/plan_*/batch_optimize.json
  2. run_batch 5 times → output to loop1/plan_a/, plan_b/, ...
  3. Aggregate → loop1/aggregate_report.md
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

LOOP1 = Path(__file__).resolve().parent
LAB_DIR = LOOP1.parent.parent  # momentum-lab

PLANS = ["plan_a", "plan_b", "plan_c", "plan_d", "plan_e"]


def run_cmd(cmd: list[str], cwd: Path) -> int:
    r = subprocess.run(cmd, cwd=cwd)
    return r.returncode


def gen_batches() -> None:
    print("=== 1. Generate batch JSON per group ===")
    r = run_cmd(
        [sys.executable, str(LOOP1 / "gen_batch_per_group.py")],
        cwd=LAB_DIR.parent,
    )
    if r != 0:
        sys.exit(r)


def run_batch_per_plan(plan: str, workers: int = 14) -> int:
    batch_path = LOOP1 / plan / "batch_optimize.json"
    if not batch_path.exists():
        print(f"  SKIP {plan}: {batch_path} not found (run gen_batch_per_group first)")
        return 1
    out_dir = LOOP1 / plan
    etf_root = LAB_DIR.parent
    return run_cmd(
        [
            "uv", "run", "python",
            str(LAB_DIR / "run_batch.py"),
            str(batch_path),
            "-o", str(out_dir),
            "--name", plan,
            "--workers", str(workers),
        ],
        cwd=etf_root,
    )


def aggregate() -> None:
    print("\n=== 3. Aggregate reports ===")
    all_rows = []
    param_used = None
    for plan in PLANS:
        results_path = LOOP1 / plan / "results.json"
        report_path = LOOP1 / plan / "report.md"
        if not results_path.exists():
            print(f"  SKIP {plan}: no results.json")
            continue
        with open(results_path, encoding="utf-8") as f:
            results = json.load(f)
        for r in results:
            cfg = r.get("config", {})
            m0 = r.get("momentum_spread0", {})
            row = {
                "plan": plan,
                "group_name": cfg.get("group_name", ""),
                "n_long": cfg.get("n_long"),
                "mom0_cagr": m0.get("cagr_pct"),
                "mom0_sharpe": m0.get("sharpe"),
                "mom0_maxdd": m0.get("max_drawdown_pct"),
            }
            all_rows.append(row)
        if report_path.exists() and param_used is None:
            # Snag param section from first report
            txt = report_path.read_text(encoding="utf-8")
            if "## Params Used" in txt:
                idx = txt.find("## Params Used")
                end = txt.find("## ", idx + 5) or len(txt)
                param_used = txt[idx:end].strip()

    if not all_rows:
        print("  No results to aggregate")
        return

    # Sort by sharpe desc
    all_rows.sort(key=lambda x: (x.get("mom0_sharpe") or 0), reverse=True)

    lines = [
        "# Aggregate: 5 Plans × Batch Optimize",
        "",
        f"Total configs: {len(all_rows)}",
        "",
    ]
    if param_used:
        lines.extend([param_used, ""])
    lines.extend([
        "## Top 30 by Momentum Sharpe",
        "",
        "| plan | group_name | n_long | mom0_cagr | mom0_sharpe | mom0_maxdd |",
        "|------|------------|--------|-----------|-------------|------------|",
    ])
    for r in all_rows[:30]:
        cagr = r.get("mom0_cagr") or 0
        sharpe = r.get("mom0_sharpe") or 0
        maxdd = r.get("mom0_maxdd") or 0
        lines.append(f"| {r.get('plan','')} | {r.get('group_name','')} | {r.get('n_long','')} | {cagr:.2f}% | {sharpe:.2f} | {maxdd:.2f}% |")
    lines.extend(["", "## Best per Plan", ""])
    best_per_plan = {}
    for r in all_rows:
        p = r.get("plan", "")
        if p not in best_per_plan or (r.get("mom0_sharpe") or 0) > (best_per_plan[p].get("mom0_sharpe") or 0):
            best_per_plan[p] = r
    lines.append("| plan | group_name | mom0_sharpe | mom0_cagr | mom0_maxdd |")
    lines.append("|------|------------|-------------|-----------|------------|")
    for plan in PLANS:
        r = best_per_plan.get(plan)
        if r:
            lines.append(f"| {plan} | {r.get('group_name','')} | {r.get('mom0_sharpe',0):.2f} | {(r.get('mom0_cagr') or 0):.2f}% | {(r.get('mom0_maxdd') or 0):.2f}% |")
        else:
            lines.append(f"| {plan} | - | - | - | - |")

    out_path = LOOP1 / "aggregate_report.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  {out_path}")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-gen", action="store_true", help="Skip gen_batch_per_group")
    parser.add_argument("--skip-batch", action="store_true", help="Skip run_batch (only aggregate)")
    parser.add_argument("--workers", type=int, default=14)
    args = parser.parse_args()

    if not args.skip_gen:
        gen_batches()
    else:
        print("=== Skip gen (--skip-gen) ===")

    if not args.skip_batch:
        print("\n=== 2. Run batch per plan ===")
        for plan in PLANS:
            print(f"  Running {plan}...")
            run_batch_per_plan(plan, workers=args.workers)
    else:
        print("=== Skip batch (--skip-batch) ===")

    aggregate()


if __name__ == "__main__":
    main()
