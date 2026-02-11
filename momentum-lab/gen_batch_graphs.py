#!/usr/bin/env python3
"""
Generate Graph 1 (2D scatter) and Graph 2 (parallel coordinates) from batch results.

Usage:
  uv run python momentum-lab/gen_batch_graphs.py <batch_path>

  batch_path:
    - Dir with results (e.g. result/momentum-lab/_batch/optimize-13etf)
      Must contain results.json (and ideally configs.json for short_weight/corr_threshold).
    - Batch config JSON: resolves to result/momentum-lab/_batch/{stem}/
      Stem must match the batch output dir name used by run_batch.py.

  Missing info:
    - If results.json absent: run run_batch.py first.
    - If configs.json absent: short_weight/corr_threshold use defaults (0.30, 1.0).
      Charts still generate; Graph 1 may show uniform short_weight if configs lacked it.

Output:
  {batch_dir}/graph1_scatter.html   # X=n_long, Y=short_weight, color=mom0 Sharpe
  {batch_dir}/graph2_parcoords.html # dims: n_long, short_weight, corr_threshold, spread_pct
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_lab_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_lab_dir))

BATCH_BASE = _lab_dir.parent / "result" / "momentum-lab" / "_batch"

# Default Config values for missing keys (from param file)
def _get_defaults(param_file: str | None = None) -> dict:
    from simulate import load_quantpedia_params
    p = load_quantpedia_params(param_file)
    if isinstance(p.get("mom_periods_days"), list):
        p = {**p, "mom_periods_days": tuple(p["mom_periods_days"])}
    return p




def resolve_batch_dir(path: Path) -> Path:
    """Resolve batch_path to directory containing results.json and configs.json."""
    p = path.resolve()
    if p.is_dir():
        if not (p / "results.json").exists() and not (p / "results.csv").exists():
            raise SystemExit(
                f"Batch dir {p} missing results.json and results.csv. "
                "Run run_batch.py first to generate results."
            )
        return p
    if p.is_file():
        batch_name = p.stem
        out = BATCH_BASE / batch_name
        if not out.exists():
            raise SystemExit(
                f"Batch output dir {out} not found. "
                "Pass a batch output dir path or run run_batch.py first."
            )
        return out
    raise SystemExit(f"Path not found: {path}")


def load_batch_data(batch_dir: Path, param_file: str | None = None) -> list[dict]:
    """Load and merge results + configs. param_file: for missing keys (default: quantpedia.json)."""
    results_path = batch_dir / "results.json"
    configs_path = batch_dir / "configs.json"

    if not results_path.exists():
        raise SystemExit(
            f"results.json not found in {batch_dir}. "
            "Graphs require results.json (run_batch.py creates it)."
        )

    defaults = _get_defaults(param_file)

    with open(results_path, encoding="utf-8") as f:
        results = json.load(f)

    configs_by_group: dict[str, dict] = {}
    if configs_path.exists():
        with open(configs_path, encoding="utf-8") as f:
            configs_raw = json.load(f)
        configs_list = configs_raw if isinstance(configs_raw, list) else configs_raw.get("configs", [])
        for c in configs_list:
            g = c.get("group_name")
            if g:
                configs_by_group[g] = c

    rows = []
    for r in results:
        cfg = r.get("config", {})
        group_name = cfg.get("group_name", "")
        override = configs_by_group.get(group_name, {})

        merged = {**defaults}
        merged.update(cfg)
        merged.update(override)

        m0 = r.get("momentum_spread0", {})
        m15 = r.get("momentum_spread", {})

        mom_days = merged.get("mom_periods_days", defaults["mom_periods_days"])
        if isinstance(mom_days, list):
            mom_str = "-".join(map(str, mom_days))
        elif isinstance(mom_days, (tuple, list)):
            mom_str = "-".join(map(str, mom_days))
        else:
            mom_str = str(mom_days)

        rows.append({
            "group_name": group_name,
            "n_long": merged.get("n_long", defaults["n_long"]),
            "n_short": merged.get("n_short", defaults["n_short"]),
            "short_weight": merged.get("short_weight", defaults["short_weight"]),
            "corr_threshold": merged.get("corr_threshold", defaults["corr_threshold"]),
            "spread_pct": merged.get("spread_pct", defaults["spread_pct"]),
            "mom_periods": mom_str,
            "mom0_sharpe": m0.get("sharpe"),
            "mom0_cagr": m0.get("cagr_pct"),
            "mom0_maxdd": m0.get("max_drawdown_pct"),
            "mom_sharpe": m15.get("sharpe"),
            "mom_cagr": m15.get("cagr_pct"),
            "mom_maxdd": m15.get("max_drawdown_pct"),
        })
    return rows


def graph1_scatter(rows: list[dict], out_path: Path) -> None:
    """Graph 1: 2D scatter — X=n_long, Y=short_weight, color=Sharpe."""
    try:
        import plotly.graph_objects as go
    except ImportError as e:
        raise ImportError("Plotly required: pip install plotly") from e

    x_vals = [r["n_long"] for r in rows]
    y_vals = [r["short_weight"] for r in rows]
    sharpe_vals = [r["mom0_sharpe"] if r["mom0_sharpe"] is not None else 0 for r in rows]
    text_vals = [r["group_name"] for r in rows]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_vals,
        y=y_vals,
        mode="markers",
        marker=dict(
            size=12,
            color=sharpe_vals,
            colorscale="Viridis",
            colorbar=dict(title="mom0 Sharpe"),
            showscale=True,
        ),
        text=text_vals,
        hovertemplate="%{text}<br>n_long=%{x}<br>short_weight=%{y}<extra></extra>",
    ))
    fig.update_layout(
        title="Graph 1: n_long × short_weight (color = mom0 Sharpe)",
        xaxis_title="n_long",
        yaxis_title="short_weight",
        template="plotly_white",
        height=500,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out_path))


def graph2_parcoords(rows: list[dict], out_path: Path) -> None:
    """Graph 2: Parallel coordinates — dims: n_long, short_weight, corr_threshold, spread_pct, mom_periods; color by Sharpe."""
    try:
        import plotly.graph_objects as go
    except ImportError as e:
        raise ImportError("Plotly required: pip install plotly") from e

    # Build dimension labels and values; parcoords needs numeric dims
    # mom_periods is categorical — map to integers or drop for parcoords
    dim_cols = ["n_long", "short_weight", "corr_threshold", "spread_pct"]
    dim_labels = dim_cols.copy()
    dim_vals = {k: [r[k] for r in rows] for k in dim_cols}
    sharpe = [r["mom0_sharpe"] if r["mom0_sharpe"] is not None else 0 for r in rows]

    dims = []
    for col in dim_cols:
        vals = dim_vals[col]
        dims.append(dict(
            label=col,
            values=vals,
            range=[min(vals), max(vals)] if vals else [0, 1],
        ))

    fig = go.Figure(data=go.Parcoords(
        dimensions=dims,
        line=dict(
            color=sharpe,
            colorscale="Viridis",
            showscale=True,
            colorbar=dict(title="mom0 Sharpe"),
        ),
    ))
    fig.update_layout(
        title="Graph 2: Parallel Coordinates (color = mom0 Sharpe)",
        template="plotly_white",
        height=500,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out_path))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate batch graphs from run_batch output")
    parser.add_argument("batch_path", type=Path, help="Batch output dir or batch config JSON path")
    parser.add_argument("--param", type=str, default="",
                        help="Param file in param/ for missing keys (default: quantpedia.json)")
    args = parser.parse_args()

    batch_dir = resolve_batch_dir(args.batch_path)
    param_file = args.param or None
    rows = load_batch_data(batch_dir, param_file=param_file)

    if not rows:
        raise SystemExit(f"No results in {batch_dir}")

    out1 = batch_dir / "graph1_scatter.html"
    out2 = batch_dir / "graph2_parcoords.html"
    graph1_scatter(rows, out1)
    graph2_parcoords(rows, out2)
    print(f"Saved {out1}")
    print(f"Saved {out2}")


if __name__ == "__main__":
    main()
