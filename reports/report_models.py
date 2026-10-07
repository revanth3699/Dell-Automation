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
