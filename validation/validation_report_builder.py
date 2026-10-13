"""Renders one self-contained HTML report comparing a Dell Migrate PDF report's own
claims ("Files copied", "Settings copied") against what's actually on this PC right
now -- validation/output/<report-name>_validation_<timestamp>.html, no sidecar files,
same "the report is the only artifact" convention reports/html_report_builder.py
uses for the main automation's own run reports. Deliberately a separate renderer (not
a shared import from reports/) -- validation/ has its own data shapes
(report_models.py) and isn't part of the UI-automation run itself.
"""

import html
import math
from pathlib import Path

from validation.report_models import ValidationRunResult

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

_PASS_COLOR = "#0ca30c"
_FAIL_COLOR = "#d03b3b"
_NEUTRAL_COLOR = "#8a8a8a"

_STATUS_LABELS = {
    "match": ("OK", "pass"),
    "mismatch": ("MISMATCH", "fail"),
    "not_registry_based": ("N/A", "neutral"),
    "no_backup_data": ("N/A", "neutral"),
    "no_mapping": ("N/A", "neutral"),
}

_STYLE = """
:root { color-scheme: light dark; --donut-track: #e1e0d9; }
@media (prefers-color-scheme: dark) { :root { --donut-track: #2c2c2a; } }
body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; padding: 2rem;
       background: #fafafa; color: #1a1a1a; }
@media (prefers-color-scheme: dark) { body { background: #1a1a1a; color: #eee; } }
h1 { font-size: 1.4rem; margin-bottom: 0.25rem; }
h2 { font-size: 1.1rem; margin-top: 2rem; }
.subtitle { color: #777; margin-bottom: 1.5rem; word-break: break-all; }
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
.overall-badge { font-size: 1rem; font-weight: 700; padding: 0.3rem 0.9rem; border-radius: 6px; }
.overall-badge.pass { background: #dafbe1; color: #0ca30c; }
.overall-badge.fail { background: #ffebe9; color: #d03b3b; }
table { border-collapse: collapse; width: 100%; margin-top: 0.5rem; }
td, th { text-align: left; padding: 0.4rem 0.7rem; border-bottom: 1px solid rgba(127,127,127,0.15); font-size: 0.9rem; }
th { color: #888; font-weight: 600; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.03em; }
.badge { font-size: 0.7rem; font-weight: 700; padding: 0.1rem 0.5rem; border-radius: 4px; white-space: nowrap; }
.badge.pass { background: #dafbe1; color: #0ca30c; }
.badge.fail { background: #ffebe9; color: #d03b3b; }
.badge.neutral { background: rgba(127,127,127,0.15); color: #8a8a8a; }
.mono { font-family: ui-monospace, Consolas, monospace; font-size: 0.85rem; }
.note { color: #777; font-size: 0.85rem; }
.category { border: 1px solid rgba(127,127,127,0.25); border-radius: 8px; margin-bottom: 0.6rem; overflow: hidden; }
.category-header { padding: 0.6rem 1rem; display: flex; align-items: center; gap: 0.7rem; cursor: pointer; }
.category-header .chevron { color: #888; font-size: 0.7rem; transition: transform 0.15s ease; }
.category-header.open .chevron { transform: rotate(90deg); }
.category-name { font-weight: 500; flex: 1; }
.category-meta { color: #888; font-size: 0.8rem; }
.category-body { padding: 0 1rem 0.8rem 1rem; }
.collapsible-body.collapsed { display: none; }
.info-list { font-size: 0.9rem; }
.info-list li { margin-bottom: 0.3rem; }
"""

_SCRIPT = """
document.querySelectorAll('.category-header').forEach(function (h) {
  var body = h.nextElementSibling;
  var hasBody = body && body.classList.contains('collapsible-body');
  if (!hasBody) { return; }
  h.classList.add('open');
  h.addEventListener('click', function () {
    body.classList.toggle('collapsed');
    h.classList.toggle('open');
  });
});
"""


def _donut_chart(passed: int, failed: int) -> str:
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
      <svg viewBox="0 0 100 100" class="donut" role="img" aria-label="Match rate {pct_label.replace('&ndash;', '0')}">
        <circle cx="50" cy="50" r="{r}" fill="none" stroke="var(--donut-track)" stroke-width="14"></circle>
        <circle cx="50" cy="50" r="{r}" fill="none" stroke="{_FAIL_COLOR}" stroke-width="14"
                stroke-dasharray="{fail_len:.2f} {circumference:.2f}" stroke-dashoffset="{-pass_len:.2f}"
                transform="rotate(-90 50 50)" stroke-linecap="butt"></circle>
        <circle cx="50" cy="50" r="{r}" fill="none" stroke="{_PASS_COLOR}" stroke-width="14"
                stroke-dasharray="{pass_len:.2f} {circumference:.2f}" stroke-dashoffset="0"
                transform="rotate(-90 50 50)" stroke-linecap="butt"></circle>
        <text x="50" y="47" text-anchor="middle" class="donut-pct">{pct_label}</text>
        <text x="50" y="62" text-anchor="middle" class="donut-sub">match rate</text>
      </svg>
      <div class="legend">
        <div class="legend-row"><span class="dot pass"></span>Matched &mdash; {passed}</div>
        <div class="legend-row"><span class="dot fail"></span>Mismatched/missing &mdash; {failed}</div>
      </div>
    </div>"""


def _files_table_html(result: ValidationRunResult) -> str:
    rows = []
    for f in result.files_copied:
        status_badge = '<span class="badge pass">OK</span>' if f.exists else '<span class="badge fail">MISSING</span>'
        size = f"{f.size_bytes:,} bytes" if f.size_bytes is not None else "&ndash;"
        rows.append(f"""<tr>
            <td class="mono">{html.escape(f.path)}</td>
            <td>{status_badge}</td>
            <td>{size}</td>
        </tr>""")
    if not rows:
        return "<p class=\"note\">No files claimed as copied by this report.</p>"
    return f"""
    <table>
      <tr><th>Path</th><th>Status</th><th>Size</th></tr>
      {"".join(rows)}
    </table>"""


def _files_not_migrated_html(result: ValidationRunResult) -> str:
    if not result.files_not_migrated:
        return ""
    items = "".join(
        f"<li><span class=\"mono\">{html.escape(e.path)}</span> &mdash; reason {html.escape(e.reason_code or '?')}: "
        f"{html.escape(e.reason_text)}</li>"
        for e in result.files_not_migrated
    )
    return f"""
    <h2>Files not migrated <span class="category-meta">({len(result.files_not_migrated)}, informational only -- the report itself already explains these)</span></h2>
    <ul class="info-list">{items}</ul>"""


def _category_html(cat, index: int) -> str:
    label, css_class = _STATUS_LABELS[cat.status]
    badge = f'<span class="badge {css_class}">{label}</span>'

    if cat.status in ("not_registry_based", "no_backup_data", "no_mapping"):
        meta = html.escape(cat.note)
        return f"""
        <div class="category">
          <div class="category-header">
            {badge}
            <span class="category-name">{html.escape(cat.name)}</span>
            <span class="category-meta">{meta}</span>
          </div>
        </div>"""

    mismatches = [r for r in cat.results if not r.matches]
    skipped = [r for r in cat.results if r.skipped_reason]
    meta = f"{len(cat.results) - len(mismatches)}/{len(cat.results)} values match"
    if skipped:
        meta += f" &middot; {len(skipped)} skipped (volatile)"

    body_id = f"cat-body-{index}"
    if not mismatches:
        return f"""
        <div class="category">
          <div class="category-header">
            {badge}
            <span class="category-name">{html.escape(cat.name)}</span>
            <span class="category-meta">{meta}</span>
          </div>
        </div>"""

    rows = []
    for r in mismatches:
        exp = r.expectation
        live = "missing" if not r.found else html.escape(repr(r.live_data))
        rows.append(f"""<tr>
            <td class="mono">{html.escape(exp.key_path)}</td>
            <td class="mono">{html.escape(exp.value_name or '(default)')}</td>
            <td class="mono">{html.escape(repr(exp.expected_data))}</td>
            <td class="mono">{live}</td>
        </tr>""")

    return f"""
    <div class="category">
      <div class="category-header" data-target="{body_id}">
        <span class="chevron">&#9656;</span>
        {badge}
        <span class="category-name">{html.escape(cat.name)}</span>
        <span class="category-meta">{meta}</span>
      </div>
      <div id="{body_id}" class="category-body collapsible-body">
        <table>
          <tr><th>Registry key</th><th>Value</th><th>Expected (backed up)</th><th>Live (actual)</th></tr>
          {"".join(rows)}
        </table>
      </div>
    </div>"""


def _settings_not_migrated_html(result: ValidationRunResult) -> str:
    if not result.settings_not_migrated:
        return ""
    items = "".join(
        f"<li>{html.escape(name)} &mdash; the report itself already reports this as failed</li>"
        for name in result.settings_not_migrated
    )
    return f"""
    <h2>Settings not migrated <span class="category-meta">({len(result.settings_not_migrated)}, informational only)</span></h2>
    <ul class="info-list">{items}</ul>"""


def _render_html(result: ValidationRunResult) -> str:
    files_total = len(result.files_copied)
    files_missing = result.files_missing_count
    settings_checkable = [c for c in result.settings_copied if c.status in ("match", "mismatch")]
    settings_mismatched = result.categories_mismatched_count

    donut_passed = (files_total - files_missing) + (len(settings_checkable) - settings_mismatched)
    donut_failed = files_missing + settings_mismatched

    overall_badge = (
        '<span class="overall-badge pass">PASS</span>' if result.all_ok
        else '<span class="overall-badge fail">FAIL</span>'
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Migration validation: {html.escape(result.report_path.parent.name)}</title>
<style>{_STYLE}</style>
</head>
<body>
  <h1>Migration Validation Report</h1>
  <div class="subtitle">Source report: {html.escape(str(result.report_path))}<br>Generated: {html.escape(result.generated_at)}</div>
  <div class="top-row">
    <div class="summary">
      <div class="stat"><span class="num">{files_total}</span>Files claimed copied</div>
      <div class="stat {'fail' if files_missing else 'pass'}"><span class="num">{files_missing}</span>Files missing</div>
      <div class="stat"><span class="num">{len(settings_checkable)}</span>Settings categories checked</div>
      <div class="stat {'fail' if settings_mismatched else 'pass'}"><span class="num">{settings_mismatched}</span>Categories mismatched</div>
      <div class="stat">{overall_badge}</div>
    </div>
    {_donut_chart(donut_passed, donut_failed)}
  </div>

  <h2>Files copied <span class="category-meta">({files_total} claimed by the report)</span></h2>
  {_files_table_html(result)}
  {_files_not_migrated_html(result)}

  <h2>Settings copied <span class="category-meta">({len(result.settings_copied)} claimed by the report)</span></h2>
  {"".join(_category_html(c, i) for i, c in enumerate(result.settings_copied)) or '<p class="note">No settings claimed as copied by this report.</p>'}
  {_settings_not_migrated_html(result)}

  <script>{_SCRIPT}</script>
</body>
</html>"""


def build_validation_report(result: ValidationRunResult) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_name = result.report_path.stem
    timestamp = result.generated_at.replace(":", "").replace("-", "")
    out_path = OUTPUT_DIR / f"{report_name}_validation_{timestamp}.html"
    out_path.write_text(_render_html(result), encoding="utf-8")
    return out_path
