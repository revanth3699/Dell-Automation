"""Renders one self-contained report file per run: reports/output/<run_id>_<role>_
<datetime>.html, built directly from reports/action_reporter.py's in-memory
ActionReporter.current() -- no actions.jsonl, no meta.json, no screenshots/ folder.
The report is the only source of truth for a run: screenshots are embedded as base64
data URIs in the page itself, and a small hidden JSON block inside the page carries the
summary stats (run_id, role, totals, pass_rate) back out for reports/output/index.html
to read -- so even the cross-run index has no sidecar files to go stale against.

Hand-written string templating -- no jinja2/CDN dependency, kept to one template.
Called from pytest_sessionfinish (tests/conftest.py) and at the end of a live
orchestration/role_runner.py run (RoleRunner.run()'s finally).
"""

import html
import json
import math
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from reports.action_reporter import ActionReporter, OUTPUT_DIR
from reports.report_models import ActionRecord, RunReport

# Status palette (pass/fail is a state, not a categorical series) -- validated via the
# dataviz skill's palette.md: good/critical, same hex on light and dark surfaces.
_PASS_COLOR = "#0ca30c"
_FAIL_COLOR = "#d03b3b"

# Generic, single source of truth for turning a BaseComponent action name into a
# human-readable phrase -- e.g. "SignInButton clicked" instead of "SignInButton.click".
# Covers every action BaseComponent currently has; an unknown future one still renders
# sensibly via the fallback (underscores -> spaces) rather than needing an edit here.
_ACTION_VERBS = {
    "click": "clicked",
    "click_at_center": "clicked",
    "type": "typed into",
    "get_text": "read",
}


def _humanize_action(component: str, action: str) -> str:
    verb = _ACTION_VERBS.get(action, action.replace("_", " "))
    return f"{html.escape(component)} {html.escape(verb)}"


def _build_run_report(reporter: ActionReporter) -> RunReport:
    records = reporter.records
    total = len(records)
    passed = sum(1 for r in records if r.status == "pass")
    failed = total - passed
    pass_rate = (passed / total * 100) if total else 0.0
    started_at = records[0].timestamp if records else None
    ended_at = records[-1].timestamp if records else None
    return RunReport(
        run_id=reporter.run_id, role=reporter.role, started_at=started_at, ended_at=ended_at,
        total=total, passed=passed, failed=failed, pass_rate=pass_rate, records=records,
    )


def _group_records(records: List[ActionRecord]) -> Dict[str, List[ActionRecord]]:
    """Groups by test_name when present (pytest runs) -- distinguishing which test
    produced which actions is genuinely useful there, and pytest tests run to completion
    one at a time, so they don't interleave the same component across widely-separated
    points in time the way a live orchestration run can.

    For a live run (no test_name), returns ONE flat group in true chronological order
    instead of grouping by component. Confirmed live (2026-10-07/08): grouping by
    component pulled two BrowserWindowCloseButton clicks 87 seconds apart (with several
    other actions genuinely happening in between -- OtpCancelButton, SignInFailedRetryButton,
    a full second sign-in pass) next to each other, while the actions that chronologically
    separated them ended up rendered further down the page -- actively misleading about
    execution order, which is the one thing a live run's report needs to get right.
    """
    if any(r.test_name for r in records):
        groups: Dict[str, List[ActionRecord]] = {}
        for r in records:
            groups.setdefault(r.test_name or "(ungrouped)", []).append(r)
        return groups
    return {"All actions (chronological)": records}


def _status_badge(status: str) -> str:
    cls = "pass" if status == "pass" else "fail"
    label = "PASS" if status == "pass" else "FAIL"
    return f'<span class="badge {cls}">{label}</span>'


def _screenshot_html(screenshot_b64: Optional[str], screenshot_error: Optional[str] = None) -> str:
    """Embeds the screenshot inline as a base64 data URI -- never a reference to a
    screenshots/ folder, since the report is the only file a run produces.

    Shows WHY capture failed when known (confirmed live 2026-10-07: a window-closing
    action's own screenshot can race the window actually closing -- the action itself
    still reports PASS, but there's genuinely nothing left to capture by that point).
    Previously this was a bare, unexplained "no screenshot" even when the reason was
    known and non-alarming."""
    if not screenshot_b64:
        if screenshot_error:
            return f'<div class="no-shot">no screenshot ({html.escape(screenshot_error)})</div>'
        return '<div class="no-shot">no screenshot</div>'
    return f'<img class="shot" src="data:image/png;base64,{screenshot_b64}" alt="screenshot">'


def _action_row_html(r: ActionRecord, index: int) -> str:
    """Each action is its own dropdown: a clickable header (badge/name/duration) and a
    collapsible body (error text, if any, plus the embedded screenshot(s)). Failed
    actions start expanded (the thing you need to see first); passed actions start
    collapsed (keeps a long run scannable) -- one click away either way, never omitted.

    click()/click_at_center() carry a before-shot too (2026-10-08) -- rendered side by
    side with the existing after-shot so a genuine before/after comparison is visible at
    a glance. Every other action type has screenshot_before=None, so this collapses back
    to the single after-shot, unchanged.
    """
    expanded = r.status == "fail"
    error_html = f'<div class="error">{html.escape(r.error)}</div>' if r.error else ""
    body_id = f"action-body-{index}"
    if r.screenshot_before is not None or r.screenshot_before_error is not None:
        shots_html = f"""
        <div class="shots-row">
          <div class="shot-col"><div class="shot-label">Before</div>{_screenshot_html(r.screenshot_before, r.screenshot_before_error)}</div>
          <div class="shot-col"><div class="shot-label">After</div>{_screenshot_html(r.screenshot, r.screenshot_error)}</div>
        </div>"""
    else:
        shots_html = _screenshot_html(r.screenshot, r.screenshot_error)
    return f"""
    <div class="action-row {r.status}">
      <div class="action-header toggle-header" data-target="{body_id}">
        <span class="chevron">&#9656;</span>
        {_status_badge(r.status)}
        <span class="action-name">{_humanize_action(r.component, r.action)}</span>
        <span class="action-meta">{r.duration_ms:.0f} ms &middot; {html.escape(r.timestamp)}</span>
      </div>
      <div id="{body_id}" class="action-body collapsible-body{'' if expanded else ' collapsed'}">
        {error_html}
        {shots_html}
      </div>
    </div>"""


def _donut_chart(passed: int, failed: int) -> str:
    """Pass/fail as a donut (percentage in the centre, a labeled legend below -- never
    color-alone identity), status-palette colors. Two-slice pies are a flagged
    anti-pattern in the dataviz skill (a stat tile is its suggested replacement, which
    this report already has) -- kept here because it was explicitly requested; the
    donut form plus the center stat and legend is the closer-to-accessible version of
    that request."""
    total = passed + failed
    r = 40
    circumference = 2 * math.pi * r
    if total == 0:
        pass_len, fail_len, pct_label = 0.0, 0.0, "&ndash;"
    else:
        pass_len = circumference * (passed / total)
        fail_len = circumference - pass_len
        pct_label = f"{passed / total * 100:.0f}%"

    return f"""
    <div class="donut-wrap">
      <svg viewBox="0 0 100 100" class="donut" role="img" aria-label="Pass rate {pct_label.replace('&ndash;', '0')}">
        <circle cx="50" cy="50" r="{r}" fill="none" stroke="var(--donut-track)" stroke-width="14"></circle>
        <circle cx="50" cy="50" r="{r}" fill="none" stroke="{_FAIL_COLOR}" stroke-width="14"
                stroke-dasharray="{fail_len:.2f} {circumference:.2f}" stroke-dashoffset="{-pass_len:.2f}"
                transform="rotate(-90 50 50)" stroke-linecap="butt"></circle>
        <circle cx="50" cy="50" r="{r}" fill="none" stroke="{_PASS_COLOR}" stroke-width="14"
                stroke-dasharray="{pass_len:.2f} {circumference:.2f}" stroke-dashoffset="0"
                transform="rotate(-90 50 50)" stroke-linecap="butt"></circle>
        <text x="50" y="47" text-anchor="middle" class="donut-pct">{pct_label}</text>
        <text x="50" y="62" text-anchor="middle" class="donut-sub">pass rate</text>
      </svg>
      <div class="legend">
        <div class="legend-row"><span class="dot pass"></span>Passed &mdash; {passed}</div>
        <div class="legend-row"><span class="dot fail"></span>Failed &mdash; {failed}</div>
      </div>
    </div>"""


_STYLE = """
:root {
  color-scheme: light dark;
  --donut-track: #e1e0d9;
}
@media (prefers-color-scheme: dark) { :root { --donut-track: #2c2c2a; } }
body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; padding: 2rem;
       background: #fafafa; color: #1a1a1a; }
@media (prefers-color-scheme: dark) { body { background: #1a1a1a; color: #eee; } }
h1 { font-size: 1.4rem; margin-bottom: 0.25rem; }
.subtitle { color: #777; margin-bottom: 1.5rem; }
.top-row { display: flex; gap: 2rem; flex-wrap: wrap; align-items: center; margin-bottom: 1.5rem; }
.summary { display: flex; gap: 1.5rem; flex-wrap: wrap; }
.stat { background: rgba(127,127,127,0.08); border-radius: 8px; padding: 0.75rem 1.25rem; min-width: 110px; }
.stat .num { font-size: 1.8rem; font-weight: 700; display: block; }
.stat.pass .num { color: #0ca30c; } .stat.fail .num { color: #d03b3b; }
.donut-wrap { display: flex; align-items: center; gap: 1rem; }
.donut { width: 110px; height: 110px; flex-shrink: 0; }
.donut-pct { font-size: 20px; font-weight: 700; fill: currentColor; }
.donut-sub { font-size: 8px; fill: #888; text-transform: uppercase; letter-spacing: 0.04em; }
.legend { font-size: 0.85rem; }
.legend-row { display: flex; align-items: center; gap: 0.4rem; margin: 0.15rem 0; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.dot.pass { background: #0ca30c; } .dot.fail { background: #d03b3b; }
.group { margin-bottom: 1.5rem; border: 1px solid rgba(127,127,127,0.25); border-radius: 8px; overflow: hidden; }
.group-header { background: rgba(127,127,127,0.08); padding: 0.6rem 1rem; font-weight: 600;
                cursor: pointer; display: flex; justify-content: space-between; }
.action-row { border-top: 1px solid rgba(127,127,127,0.15); }
.action-header { padding: 0.6rem 1rem; display: flex; align-items: center; gap: 0.6rem;
                 flex-wrap: wrap; cursor: pointer; }
.chevron { display: inline-block; transition: transform 0.15s ease; color: #888; font-size: 0.7rem; }
.action-header.open .chevron { transform: rotate(90deg); }
.action-name { font-weight: 500; }
.action-meta { color: #888; font-size: 0.8rem; margin-left: auto; }
.action-body { padding: 0 1rem 0.8rem 2.3rem; }
.badge { font-size: 0.7rem; font-weight: 700; padding: 0.1rem 0.5rem; border-radius: 4px; }
.badge.pass { background: #dafbe1; color: #0ca30c; }
.badge.fail { background: #ffebe9; color: #d03b3b; }
.error { color: #d03b3b; margin-bottom: 0.4rem; font-family: monospace; font-size: 0.85rem; white-space: pre-wrap; }
.shot { max-width: 480px; max-height: 360px; border-radius: 6px; display: block;
        border: 1px solid rgba(127,127,127,0.3); }
.no-shot { color: #999; font-size: 0.8rem; font-style: italic; }
.shots-row { display: flex; gap: 1rem; flex-wrap: wrap; }
.shot-label { font-size: 0.7rem; color: #888; text-transform: uppercase; letter-spacing: 0.04em;
              margin-bottom: 0.25rem; }
.collapsible-body.collapsed { display: none; }
"""

_SCRIPT = """
document.querySelectorAll('.toggle-header').forEach(function (h) {
  h.classList.add('open');
  var targetId = h.getAttribute('data-target');
  var body = targetId ? document.getElementById(targetId) : h.nextElementSibling;
  if (body && body.classList.contains('collapsed')) { h.classList.remove('open'); }
  h.addEventListener('click', function () {
    body.classList.toggle('collapsed');
    h.classList.toggle('open');
  });
});
document.querySelectorAll('.group-header').forEach(function (h) {
  h.addEventListener('click', function () {
    var body = h.nextElementSibling;
    body.classList.toggle('collapsed');
  });
});
"""


def _render_html(report: RunReport, generated_at: str) -> str:
    groups = _group_records(report.records)
    groups_html = []
    idx = 0
    for name, records in groups.items():
        group_passed = sum(1 for r in records if r.status == "pass")
        group_total = len(records)
        rows = []
        for r in records:
            rows.append(_action_row_html(r, idx))
            idx += 1
        groups_html.append(f"""
        <div class="group">
          <div class="group-header">
            <span>{html.escape(name)}</span>
            <span>{group_passed}/{group_total} passed</span>
          </div>
          <div class="collapsible-body">{"".join(rows)}</div>
        </div>""")

    build_path_line = ""
    build_path = os.environ.get("DDA_TARGET_BUILD_PATH") or os.environ.get("DDA_SOURCE_BUILD_PATH")
    if build_path:
        build_path_line = f'<div class="subtitle">Build: {html.escape(build_path)}</div>'

    # Hidden metadata block -- the one place a run's summary stats live, so
    # reports/output/index.html can read them back out of this same file instead of a
    # sidecar meta.json. "<\/" avoids a literal "</script>" breaking the block if a
    # run_id ever contained it.
    meta = {
        "run_id": report.run_id, "role": report.role, "generated_at": generated_at,
        "total": report.total, "passed": report.passed, "failed": report.failed,
        "pass_rate": report.pass_rate, "started_at": report.started_at, "ended_at": report.ended_at,
    }
    meta_json = json.dumps(meta).replace("</", "<\\/")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Run report: {html.escape(report.run_id)} ({html.escape(report.role)})</title>
<style>{_STYLE}</style>
</head>
<body>
  <script type="application/json" id="run-meta">{meta_json}</script>
  <h1>Dell Data Assistant Automation &mdash; Run Report</h1>
  <div class="subtitle">run_id: {html.escape(report.run_id)} &middot; role: {html.escape(report.role)}
    &middot; {html.escape(report.started_at or "-")} &rarr; {html.escape(report.ended_at or "-")}</div>
  {build_path_line}
  <div class="top-row">
    <div class="summary">
      <div class="stat"><span class="num">{report.total}</span>Total actions</div>
      <div class="stat pass"><span class="num">{report.passed}</span>Passed</div>
      <div class="stat fail"><span class="num">{report.failed}</span>Failed</div>
      <div class="stat"><span class="num">{report.pass_rate:.1f}%</span>Pass rate</div>
    </div>
    {_donut_chart(report.passed, report.failed)}
  </div>
  <h2>Actions</h2>
  {"".join(groups_html) if groups_html else "<p>No actions recorded for this run.</p>"}
  <script>{_SCRIPT}</script>
</body>
</html>"""


def build_report() -> Path:
    """Renders the current run (ActionReporter.current()) to one flat file:
    reports/output/<run_id>_<role>_<YYYYmmdd-HHMMSS>.html -- no folder, no sidecar
    files. Safe to call once at the end of a run (pytest_sessionfinish,
    RoleRunner.run()'s finally)."""
    reporter = ActionReporter.current()
    report = _build_run_report(reporter)
    generated_at = reporter.started_at_dt.strftime("%Y-%m-%dT%H:%M:%S")
    datetime_suffix = reporter.started_at_dt.strftime("%Y%m%d-%H%M%S")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html_path = OUTPUT_DIR / f"{reporter.run_id}_{reporter.role}_{datetime_suffix}.html"
    html_path.write_text(_render_html(report, generated_at), encoding="utf-8")

    _build_index()
    return html_path


_META_RE = re.compile(
    r'<script type="application/json" id="run-meta">(.*?)</script>', re.DOTALL
)


def _build_index() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    runs = []
    for report_path in OUTPUT_DIR.glob("*.html"):
        if report_path.name == "index.html":
            continue
        try:
            text = report_path.read_text(encoding="utf-8")
            match = _META_RE.search(text)
            if not match:
                continue
            meta = json.loads(match.group(1).replace("<\\/", "</"))
            meta["_file"] = report_path.name
            runs.append(meta)
        except Exception:
            continue  # a malformed/unrelated .html file must never break the index
    runs.sort(key=lambda m: m.get("generated_at", ""), reverse=True)

    rows = "".join(
        f"""<tr>
              <td>{html.escape(r['run_id'])}</td><td>{html.escape(r['role'])}</td>
              <td>{html.escape(r.get('generated_at', '-'))}</td>
              <td>{r['passed']}/{r['total']} ({r['pass_rate']:.1f}%)</td>
              <td><a href="{html.escape(r['_file'])}">open</a></td>
            </tr>"""
        for r in runs
    )
    index_html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Automation run reports</title>
<style>{_STYLE}
table {{ border-collapse: collapse; width: 100%; max-width: 900px; }}
td, th {{ text-align: left; padding: 0.4rem 0.8rem; border-bottom: 1px solid rgba(127,127,127,0.2); }}
</style></head>
<body>
  <h1>Automation run reports</h1>
  <table>
    <tr><th>Run ID</th><th>Role</th><th>Generated</th><th>Pass rate</th><th></th></tr>
    {rows}
  </table>
</body></html>"""
    (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")
