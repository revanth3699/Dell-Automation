"""Shared local state-file contract between flows/target/reminder_flow.py (writer) and
utils/notifications/listener.py (reader) -- one JSON file per pending reminder, under
reports/output/<run_id>_notification_state.json.

Centralized here (not duplicated in both the writer and reader, which is how this
started) so both sides can only ever agree on the schema -- see the notification-
automation plan's Design Sec 6 for why this file exists (it carries run_id across the
gap between "reminder set" and "notification fires," and gives the deadline-fallback
path something to check).

Each state file also records its OWN "scenario" (an orchestration/role_runner.py
SCENARIOS key) to run once resumed -- decided by whoever set the reminder, not by
whatever rule the listener happens to match against a live notification. See rules.py's
module docstring for why those two are kept independent.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = REPO_ROOT / "reports" / "output"

DEFAULT_SCENARIO = "full_transfer"  # see rules.py's module docstring: "for now", per
                                     # explicit user direction, since Dell hasn't
                                     # delivered the real notification-click-to-relaunch
                                     # integration yet. Switch to
                                     # "target_notification_resume" once it does.


def state_path_for(run_id: str) -> Path:
    return STATE_DIR / f"{run_id}_notification_state.json"


def write_pending(run_id: str, notification_type: str, expected_fire_by: datetime, scenario: str = DEFAULT_SCENARIO) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = state_path_for(run_id)
    path.write_text(json.dumps({
        "run_id": run_id,
        "notification_type": notification_type,
        "set_at": datetime.now(timezone.utc).isoformat(),
        "expected_fire_by": expected_fire_by.isoformat(),
        "scenario": scenario,
        "status": "pending",
    }))
    return path


def find_pending_state_files() -> list[Path]:
    if not STATE_DIR.is_dir():
        return []
    return sorted(STATE_DIR.glob("*_notification_state.json"))


def read_state(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def mark_resumed(path: Path, state: dict, reason: str) -> None:
    state["status"] = "resumed"
    state["resumed_reason"] = reason
    path.write_text(json.dumps(state))
