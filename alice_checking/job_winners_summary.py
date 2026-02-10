"""job_winners_summary.py -- Job 014: Summarize all winners across jobs.

This job does NOT run any backtests.
It reads the shared result/alice_checking/compare_result.md scoreboard,
then writes:
  - result/alice_checking/job-plan-014-winners_summary.md
  - result/alice_checking/job-result-014-winners_summary.md
and appends a per-job section to compare_result.md.

Usage:
  cd /home/zoftdev/clawd/workspace/etf
  uv run python alice_checking/job_winners_summary.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from alice_checking.compare_utils import (
    SCOREBOARD_END,
    SCOREBOARD_START,
    append_job_section,
)

OUT_DIR = project_root / "result" / "alice_checking"
COMPARE_MD = OUT_DIR / "compare_result.md"

JOB_ID = "014"
NAME = "winners_summary"


def _parse_scoreboard_rows(md: str) -> list[dict]:
    """Parse markdown table rows between SCOREBOARD markers."""
    if SCOREBOARD_START not in md or SCOREBOARD_END not in md:
        return []

    body = md.split(SCOREBOARD_START, 1)[1].split(SCOREBOARD_END, 1)[0]
    rows = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        # skip header/separator
        if "variant" in line and "avg_cagr" in line:
            continue
        if set(line.replace("|", "").strip()) <= {"-", " "}:
            continue

        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) != 8:
            continue

        variant, family, avg_cagr, avg_sharpe, avg_mdd, beat_cagr, beat_sharpe, job = parts
        try:
            rows.append(
                {
                    "variant": variant,
                    "family": family,
                    "avg_cagr": float(avg_cagr),
                    "avg_sharpe": float(avg_sharpe),
                    "avg_mdd": float(avg_mdd),
                    "beat_cagr": beat_cagr,
                    "beat_sharpe": beat_sharpe,
                    "job": job,
                }
            )
        except Exception:
            continue
    return rows


def write_plan(start: datetime) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"job-plan-{JOB_ID}-{NAME}.md"
    path.write_text(
        "\n".join(
            [
                f"# Job Plan: {JOB_ID}-{NAME}",
                f"- **Job ID:** {JOB_ID}",
                f"- **Started:** {start:%Y-%m-%d %H:%M:%S}",
                "- **Status:** RUNNING",
                "",
                "## Objective",
                "Summarize all scoreboard winners across all completed jobs.",
                "",
                "## Inputs",
                f"- {COMPARE_MD.relative_to(project_root)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def write_result(start: datetime, end: datetime, winners: list[dict]) -> Path:
    duration = int((end - start).total_seconds())
    path = OUT_DIR / f"job-result-{JOB_ID}-{NAME}.md"

    winners_by_cagr = sorted(winners, key=lambda x: x["avg_cagr"], reverse=True)
    winners_by_sharpe = sorted(winners, key=lambda x: x["avg_sharpe"], reverse=True)

    # family counts
    fam_counts: dict[str, int] = {}
    for w in winners:
        fam_counts[w["family"]] = fam_counts.get(w["family"], 0) + 1
    fam_lines = [f"- {fam}: {cnt}" for fam, cnt in sorted(fam_counts.items(), key=lambda x: (-x[1], x[0]))]

    def top_table(items: list[dict], title: str) -> list[str]:
        lines = [f"## {title}", "", "| variant | family | avg_cagr | avg_sharpe | avg_mdd | job |", "|---|---:|---:|---:|---:|---:|"]
        for w in items[:15]:
            lines.append(
                f"| {w['variant']} | {w['family']} | {w['avg_cagr']:.2f} | {w['avg_sharpe']:.2f} | {w['avg_mdd']:.2f} | {w['job']} |"
            )
        lines.append("")
        return lines

    lines: list[str] = []
    lines += [
        f"# Job Result: {JOB_ID}-{NAME}",
        f"- **Start:** {start:%Y-%m-%d %H:%M:%S}",
        f"- **End:** {end:%Y-%m-%d %H:%M:%S}",
        f"- **Duration:** {duration}s",
        "- **Status:** COMPLETED",
        "",
        f"## Winner Count\n\nTotal winners in scoreboard: **{len(winners)}**",
        "",
        "## Winners by Family",
        "",
    ]
    lines += fam_lines if fam_lines else ["(none)"]
    lines += [""]

    if winners:
        lines += top_table(winners_by_cagr, "Top Winners by Avg CAGR")
        lines += top_table(winners_by_sharpe, "Top Winners by Avg Sharpe")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    start = datetime.now()
    write_plan(start)

    if not COMPARE_MD.exists():
        raise SystemExit(f"Missing compare_result.md at: {COMPARE_MD}")

    md = COMPARE_MD.read_text(encoding="utf-8")
    winners = _parse_scoreboard_rows(md)

    end = datetime.now()
    write_result(start, end, winners)

    # Append a per-job section to compare_result.md
    section = [
        f"## Job {JOB_ID}: {NAME}",
        "",
        f"- Completed: {end:%Y-%m-%d %H:%M:%S}",
        f"- Winners in scoreboard: **{len(winners)}**",
        "",
        f"See: `{(OUT_DIR / f'job-result-{JOB_ID}-{NAME}.md').relative_to(project_root)}`",
        "",
        "---",
        "",
    ]
    append_job_section(COMPARE_MD, section)


if __name__ == "__main__":
    main()
