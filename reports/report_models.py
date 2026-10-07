"""ActionRecord / RunReport dataclasses for the HTML report pipeline (PROJECT_PLAN.md
Sec 4.8). ActionRecord is one action, held in memory on reports/action_reporter.py's
ActionReporter for the duration of a run; RunReport is the aggregate
reports/html_report_builder.py builds from those records when rendering the final
report -- neither is persisted on its own (the rendered HTML file is the only thing
written to disk -- see action_reporter.py's module docstring).
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ActionRecord:
    run_id: str
    role: str
    component: str
    action: str
    status: str  # "pass" or "fail"
    timestamp: str  # ISO 8601
    duration_ms: float
    error: Optional[str] = None
    screenshot: Optional[str] = None  # plain base64 PNG string (no data: prefix, no file
                                       # on disk) -- the report is the only source of truth
    screenshot_error: Optional[str] = None  # why capture failed, if screenshot is None --
                                             # e.g. a window-closing action's own capture
                                             # racing the window actually closing. Confirmed
                                             # 2026-10-07: this used to be silently swallowed,
                                             # rendering as a bare, unexplained "no screenshot".
    screenshot_before: Optional[str] = None  # click()/click_at_center() only (2026-10-08):
                                              # a second screenshot taken right before the
                                              # click fires, so a report can show a genuine
                                              # before/after comparison -- the kind of
                                              # evidence that would have helped diagnose this
                                              # project's repeated "click reports success but
                                              # the button never actually activates" WebView2
                                              # bug. None for every other action type.
    screenshot_before_error: Optional[str] = None  # same as screenshot_error, for the before shot
    test_name: Optional[str] = None  # populated only under pytest (see tests/conftest.py)


@dataclass
class RunReport:
    run_id: str
    role: str
    started_at: Optional[str]
    ended_at: Optional[str]
    total: int
    passed: int
    failed: int
    pass_rate: float  # 0-100
    records: List[ActionRecord] = field(default_factory=list)
