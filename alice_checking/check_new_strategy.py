"""check_new_strategy.py -- lightweight watcher for strategy definition changes.

Goal: detect when the strategy/variant definitions change ("new strategy")
WITHOUT running any backtests.

It fingerprints the source-of-truth files:
  - checking/tool_run_variants_grid.py
  - checking/strategy_backtest_lib.py
  - alice_checking/plan.md

If the fingerprint changes, it writes:
  - result/alice_checking/new_strategy_detected.log (append)
  - result/alice_checking/strategy_watch_state.json (update)

Usage:
  cd /home/zoftdev/clawd/workspace/etf
  uv run python alice_checking/check_new_strategy.py
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent

WATCH_FILES = [
    project_root / "checking" / "tool_run_variants_grid.py",
    project_root / "checking" / "strategy_backtest_lib.py",
    project_root / "alice_checking" / "plan.md",
]

OUT_DIR = project_root / "result" / "alice_checking"
STATE_PATH = OUT_DIR / "strategy_watch_state.json"
LOG_PATH = OUT_DIR / "new_strategy_detected.log"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def compute_fingerprint() -> dict:
    files = []
    for p in WATCH_FILES:
        files.append(
            {
                "path": str(p.relative_to(project_root)),
                "sha256": sha256_file(p) if p.exists() else None,
                "exists": p.exists(),
            }
        )
    combined = hashlib.sha256(json.dumps(files, sort_keys=True).encode("utf-8")).hexdigest()
    return {"combined": combined, "files": files}


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    new_fp = compute_fingerprint()
    old = load_state()

    old_combined = old.get("combined")
    if old_combined and old_combined != new_fp["combined"]:
        LOG_PATH.write_text(
            (
                LOG_PATH.read_text(encoding="utf-8") if LOG_PATH.exists() else ""
            )
            + "\n".join(
                [
                    f"[{now:%Y-%m-%d %H:%M:%S}] NEW STRATEGY DETECTED: fingerprint changed",
                    f"old={old_combined}",
                    f"new={new_fp['combined']}",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    # first run or unchanged: just update state
    STATE_PATH.write_text(
        json.dumps(
            {
                "checked_at": f"{now:%Y-%m-%d %H:%M:%S}",
                **new_fp,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
