"""compare_utils.py -- Shared helpers for compare_result.md formatting.

Used by job_buy_hold.py and job_strategy_batch.py to write consistently
formatted sections to the shared compare_result.md file.

compare_result.md structure:
  1. Baseline thresholds table
  2. Scoreboard (between markers) -- each job inserts winner rows here
  3. Per-job detail sections (appended at the end)
"""

from __future__ import annotations

from pathlib import Path

SCOREBOARD_START = "<!-- SCOREBOARD_START -->"
SCOREBOARD_END = "<!-- SCOREBOARD_END -->"
SCOREBOARD_HEADER = (
    "| variant | family | avg_cagr | avg_sharpe | avg_mdd "
    "| beat_cagr | beat_sharpe | job |"
)
SCOREBOARD_SEP = (
    "|---------|--------|----------|------------|---------|"
    "-----------|-------------|-----|"
)


def init_compare_result(
    path: Path,
    avg_cagr: float,
    avg_sharpe: float,
    median_cagr: float,
    median_sharpe: float,
    avg_mdd: float,
    etf_count: int,
) -> None:
    """Create compare_result.md with header, baseline thresholds, and empty scoreboard."""
    lines = [
        "# Compare Result (across all jobs)",
        "",
        "_Scoreboard auto-updated as each job completes._",
        "",
        "## Baseline Thresholds (Job 001: buy_hold)",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Avg CAGR % | {avg_cagr:.2f} |",
        f"| Median CAGR % | {median_cagr:.2f} |",
        f"| Avg Sharpe | {avg_sharpe:.2f} |",
        f"| Median Sharpe | {median_sharpe:.2f} |",
        f"| Avg Max DD % | {avg_mdd:.2f} |",
        f"| ETFs | {etf_count} |",
        "",
        (
            f"_A variant **beats** buy_hold if its avg CAGR > {avg_cagr:.2f}%"
            f" OR avg Sharpe > {avg_sharpe:.2f}._"
        ),
        "",
        "---",
        "",
        "## Scoreboard: All Winners",
        "",
        SCOREBOARD_START,
        SCOREBOARD_HEADER,
        SCOREBOARD_SEP,
        SCOREBOARD_END,
        "",
        "---",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def append_winners_to_scoreboard(path: Path, winners: list[dict]) -> None:
    """Insert winner rows into scoreboard between SCOREBOARD markers.

    Each winner dict must have keys:
        variant, family, avg_cagr, avg_sharpe, avg_mdd,
        beat_cagr (bool), beat_sharpe (bool), job (str).
    """
    if not winners:
        return

    content = path.read_text(encoding="utf-8")
    new_rows = []
    for w in winners:
        row = (
            f"| {w['variant']} "
            f"| {w['family']} "
            f"| {w['avg_cagr']:.2f} "
            f"| {w['avg_sharpe']:.2f} "
            f"| {w['avg_mdd']:.2f} "
            f"| {'Y' if w['beat_cagr'] else '-'} "
            f"| {'Y' if w['beat_sharpe'] else '-'} "
            f"| {w['job']} |"
        )
        new_rows.append(row)

    insert_text = "\n".join(new_rows) + "\n"
    content = content.replace(SCOREBOARD_END, insert_text + SCOREBOARD_END)
    path.write_text(content, encoding="utf-8")


def append_job_section(path: Path, lines: list[str]) -> None:
    """Append a per-job detail section at the end of compare_result.md."""
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))
