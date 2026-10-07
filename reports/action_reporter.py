"""
ActionReporter: record(ActionRecord) -> in-memory list; capture_screenshot(...) -> a
base64 PNG string (never written to disk).

The report is the only source of truth for a run -- no screenshots/ folder, no
actions.jsonl, no meta.json. Everything accumulates in memory on this process-global
reporter while the run is in progress, and reports/html_report_builder.py renders it all
(including screenshots, embedded as base64) into one self-contained HTML file when the
run finishes. Trade-off, worth knowing: unlike the earlier jsonl-per-action design, a
crash mid-run loses whatever hasn't been rendered yet, since nothing is flushed to disk
incrementally -- accepted deliberately per the "report is the only source of truth, no
other files" requirement.

Idempotent, process-global singleton -- same shape as factory/logger_factory.py's
LoggerFactory, and for the same reason: components/base_component.py is constructed at
dozens of call sites across components/target/ and components/source/ on a bare
WinAppDriverSession (not factory/session.py's Session lifecycle object -- confirmed via
factory/session.py's own _close_browser_window(), which builds a BaseComponent directly
on one), so there is no run_id/role to thread through that chain without touching every
Page Object. Instead, whichever real entry point starts a run (orchestration/role_runner.py,
tests/conftest.py, tools/run_sign_in_flow.py) calls start_run() once; BaseComponent just
asks current() for whichever reporter is active right now.

If nothing ever calls start_run() (e.g. a throwaway tools/_test_*.py script), current()
auto-creates a default reporter on first use so recording never crashes for lack of one.
"""

import base64
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from reports.report_models import ActionRecord

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


class ActionReporter:
    _current: Optional["ActionReporter"] = None
    _lock = threading.RLock()

    def __init__(self, run_id: str, role: str):
        self.run_id = run_id
        self.role = role
        self.started_at_dt = datetime.now()
        self.records: List[ActionRecord] = []
        self._current_test_name: Optional[str] = None
        self._records_lock = threading.Lock()

    @classmethod
    def start_run(cls, run_id: str, role: str) -> "ActionReporter":
        with cls._lock:
            cls._current = cls(run_id, role)
            return cls._current

    @classmethod
    def current(cls) -> "ActionReporter":
        with cls._lock:
            if cls._current is None:
                cls._current = cls(run_id=f"unattended-{int(time.time())}", role="unspecified")
            return cls._current

    def set_test_name(self, name: Optional[str]) -> None:
        self._current_test_name = name

    def clear_test_name(self) -> None:
        self._current_test_name = None

    def record(
        self,
        component: str,
        action: str,
        status: str,
        duration_ms: float,
        error: Optional[str] = None,
        screenshot: Optional[str] = None,
    ) -> None:
        record = ActionRecord(
            run_id=self.run_id,
            role=self.role,
            component=component,
            action=action,
            status=status,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            duration_ms=duration_ms,
            error=error,
            screenshot=screenshot,
            test_name=self._current_test_name,
        )
        with self._records_lock:
            self.records.append(record)

    def capture_screenshot(self, session, component: str, action: str) -> Optional[str]:
        """Returns the screenshot as a plain base64 string (no data: prefix -- the
        report builder adds that), never touching disk. Never raises -- evidence
        capture must never mask the real failure (same rule the old disk-writing
        version followed)."""
        try:
            return base64.b64encode(session.get_screenshot_as_png()).decode("ascii")
        except Exception:
            return None
