#!/usr/bin/env python3
"""
Generate 5 batch JSON files from batch_optimize.json.
Each plan group gets its own batch with etfs overridden, group_name prefixed.

Output:
  loop1/plan_a/batch_optimize.json
  loop1/plan_b/batch_optimize.json
  ...
"""

from __future__ import annotations

import json
from pathlib import Path

LOOP1 = Path(__file__).resolve().parent
BATCH_OPTIMIZE = Path(__file__).resolve().parent.parent.parent / "batch_optimize.json"

PLANS = [
    ("plan_a", "plan_a_quantpedia.json"),
    ("plan_b", "plan_b_low_corr.json"),
    ("plan_c", "plan_c_long_backtest.json"),
    ("plan_d", "plan_d_low_expense.json"),
    ("plan_e", "plan_e_sector_tilt.json"),
]


def main() -> None:
    with open(BATCH_OPTIMIZE, encoding="utf-8") as f:
        base = json.load(f)
    base_configs = base["configs"]

    for plan_key, plan_file in PLANS:
        plan_path = LOOP1 / plan_file
        with open(plan_path, encoding="utf-8") as f:
            plan = json.load(f)
        etfs = plan["etfs"]

        out_configs = []
        for c in base_configs:
            merged = {**c, "etfs": etfs}
            merged["group_name"] = f"{plan_key}-{c['group_name']}"
            out_configs.append(merged)

        out_dir = LOOP1 / plan_key
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "batch_optimize.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"configs": out_configs}, f, indent=2, ensure_ascii=False)
        print(f"  {out_path} ({len(out_configs)} configs, {len(etfs)} ETFs)")


if __name__ == "__main__":
    print("Generating batch JSON per plan...")
    main()
    print("Done.")
