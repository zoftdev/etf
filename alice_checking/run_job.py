"""run_job.py -- Autopilot dispatcher.

Finds the next pending job, runs it, and schedules next crontab wakeup.

Usage:
  cd ~/clawd/workspace/etf
  uv run python alice_checking/run_job.py
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

RESULT_DIR = project_root / "result" / "alice_checking"
PROGRESS_FILE = Path(__file__).resolve().parent / "progress.md"
LOG_FILE = "/tmp/alice_checking.log"

# ── job queue ─────────────────────────────────────────────────────────────
# Each entry: (job_id, name, script_path, extra_args_list)
JOB_QUEUE = [
    ("001", "buy_hold", "alice_checking/job_buy_hold.py", []),
    ("002", "sma", "alice_checking/job_strategy_batch.py", ["--family", "sma", "--job-id", "002"]),
    ("003", "ema", "alice_checking/job_strategy_batch.py", ["--family", "ema", "--job-id", "003"]),
    ("004", "momentum", "alice_checking/job_strategy_batch.py", ["--family", "momentum", "--job-id", "004"]),
    ("005", "rsi", "alice_checking/job_strategy_batch.py", ["--family", "rsi", "--job-id", "005"]),
    ("006", "bollinger", "alice_checking/job_strategy_batch.py", ["--family", "bollinger", "--job-id", "006"]),
    ("007", "donchian", "alice_checking/job_strategy_batch.py", ["--family", "donchian", "--job-id", "007"]),
    ("008", "macd", "alice_checking/job_strategy_batch.py", ["--family", "macd", "--job-id", "008"]),
    ("009", "keltner", "alice_checking/job_strategy_batch.py", ["--family", "keltner", "--job-id", "009"]),
    ("010", "stochrsi", "alice_checking/job_strategy_batch.py", ["--family", "stochrsi", "--job-id", "010"]),
    ("011", "vol_target", "alice_checking/job_strategy_batch.py", ["--family", "vol_target", "--job-id", "011"]),
    ("012", "crash_filter", "alice_checking/job_strategy_batch.py", ["--family", "crash_filter", "--job-id", "012"]),
    ("013", "trend_filter", "alice_checking/job_strategy_batch.py", ["--family", "trend_filter", "--job-id", "013"]),
    ("014", "winners_summary", "alice_checking/job_winners_summary.py", []),
]


def get_completed_jobs() -> set[str]:
    """Scan result dir for completed job-result files -> set of job IDs."""
    completed = set()
    if not RESULT_DIR.exists():
        return completed
    for f in RESULT_DIR.glob("job-result-*.md"):
        # job-result-001-buy_hold.md -> 001
        parts = f.stem.split("-")
        if len(parts) >= 3:
            completed.add(parts[2])
    return completed


def find_next_job() -> tuple[str, str, str, list[str]] | None:
    """Return (job_id, name, script, args) for next pending job, or None."""
    completed = get_completed_jobs()
    for job_id, name, script, args in JOB_QUEUE:
        if job_id not in completed:
            return job_id, name, script, args
    return None


def schedule_next_wakeup():
    """Add a one-shot crontab entry for 1 minute from now."""
    now = datetime.now() + timedelta(minutes=1)
    cron_time = f"{now.minute} {now.hour} {now.day} {now.month} *"
    cron_cmd = (
        f"{cron_time} cd {project_root} && "
        f"uv run python alice_checking/run_job.py >> {LOG_FILE} 2>&1"
    )

    # read existing crontab
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""

    # remove old alice_checking entries, add new one
    lines = [l for l in existing.splitlines() if "alice_checking/run_job.py" not in l]
    lines.append(cron_cmd)
    new_crontab = "\n".join(lines) + "\n"

    subprocess.run(["crontab", "-"], input=new_crontab, text=True, check=True)
    print(f"[dispatcher] next wakeup at {now:%H:%M}")


def update_progress():
    """Rewrite progress.md with current status."""
    completed = get_completed_jobs()
    lines = ["# Alice Checking Progress", ""]
    lines.append(f"_Updated: {datetime.now():%Y-%m-%d %H:%M:%S}_")
    lines.append("")
    lines.append("| Job | Status | Result |")
    lines.append("|-----|--------|--------|")
    for job_id, name, _, _ in JOB_QUEUE:
        if job_id in completed:
            status = "COMPLETED"
            result_link = f"job-result-{job_id}-{name}.md"
        else:
            status = "pending"
            result_link = "-"
        lines.append(f"| {job_id}-{name} | {status} | {result_link} |")

    PROGRESS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    print(f"[dispatcher] wakeup at {datetime.now():%Y-%m-%d %H:%M:%S}")

    next_job = find_next_job()
    if next_job is None:
        print("[dispatcher] all jobs completed!")
        update_progress()
        return

    job_id, name, script, args = next_job
    print(f"[dispatcher] running job {job_id}-{name} ({script} {' '.join(args)})")

    # run the job script
    result = subprocess.run(
        [sys.executable, str(project_root / script)] + args,
        cwd=str(project_root),
        capture_output=False,
    )

    if result.returncode != 0:
        print(f"[dispatcher] job {job_id}-{name} exited with code {result.returncode}")

    update_progress()

    # check if there are more jobs
    if find_next_job() is not None:
        schedule_next_wakeup()
    else:
        print("[dispatcher] all jobs completed, no more wakeups")


if __name__ == "__main__":
    main()
