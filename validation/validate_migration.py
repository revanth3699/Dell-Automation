"""Standalone CLI: validates a Dell Migrate PDF migration report against the LIVE
state of this PC -- both the files it claims were copied and the registry values
behind each "Settings copied" category. Prints a console summary AND writes a
self-contained HTML report (validation/output/<report-name>_validation_<timestamp>.html)
comparing the PDF's own claims against what's actually on this PC, so that can be
shared/kept the same way the main automation's own run reports are.

Usage (run ON the Target PC, after a migration has completed):
    uv run python -m validation.validate_migration
    uv run python -m validation.validate_migration --report "<path to a specific .pdf>"
    uv run python -m validation.validate_migration --no-html

Auto-picks the most recent MigrationReport-*/*.pdf under
C:\\ProgramData\\Dell\\SupportAssist\\CDM\\Reports\\MigrationReports\\ unless --report
is given explicitly. Settings are checked against
C:\\ProgramData\\Dell\\SupportAssist\\CDM\\SettingsBackup\\, which (confirmed live,
2026-10-14) is a single shared folder reflecting only the most recent run -- the same
one the auto-picked report describes, so the two always correspond to each other.

This is deliberately a standalone script, not wired into orchestration/role_runner.py
(per explicit user direction, 2026-10-14) -- run it manually, any time after a
migration, pointed at whichever report you want to check.

Exit code: 0 if every checkable item matched; 1 if anything didn't (missing file,
registry value mismatch) or the report/backup data couldn't be found/parsed at all.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from validation.file_validator import check_files_copied
from validation.pdf_report_parser import find_latest_report, parse_report
from validation.registry_live import check_value
from validation.report_models import CategoryCheckSummary, ValidationRunResult
from validation.settings_backup import get_current_user_sid, load_category_backups
from validation.validation_report_builder import build_validation_report


def collect_results(report_path: Path = None) -> ValidationRunResult:
    """Runs every check and returns the full result set -- no printing here, so the
    exact same data can feed both the console summary and the HTML report without
    running any check twice."""
    if report_path is None:
        report_path = find_latest_report()

    report = parse_report(report_path)
    current_user_sid = get_current_user_sid()
    backups = load_category_backups(current_user_sid=current_user_sid)

    file_results = check_files_copied(report.files_copied)

    category_summaries = []
    for category_name in report.settings_copied:
        backup = backups.get(category_name)
        if backup is None:
            category_summaries.append(CategoryCheckSummary(
                name=category_name, status="no_mapping",
                note="No backup data found for this category (GUID/log mapping gap)",
            ))
            continue
        if not backup.registry_values:
            if backup.other_backup_files:
                names = ", ".join(p.name for p in backup.other_backup_files)
                category_summaries.append(CategoryCheckSummary(
                    name=category_name, status="not_registry_based",
                    note=f"Backed up via {names} -- not auto-verified yet",
                ))
            else:
                category_summaries.append(CategoryCheckSummary(
                    name=category_name, status="no_backup_data",
                    note="No backup data was captured for this category",
                ))
            continue

        results = [check_value(exp) for exp in backup.registry_values]
        status = "mismatch" if any(not r.matches for r in results) else "match"
        category_summaries.append(CategoryCheckSummary(name=category_name, status=status, results=results))

    return ValidationRunResult(
        report_path=report_path,
        generated_at=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        files_copied=file_results,
        files_not_migrated=report.files_not_migrated,
        settings_copied=category_summaries,
        settings_not_migrated=report.settings_not_migrated,
        current_user_sid=current_user_sid,
    )


def _print_header(text: str) -> None:
    print()
    print(text)
    print("=" * len(text))


def print_console_report(result: ValidationRunResult) -> None:
    print(f"Validating against report: {result.report_path}")
    if result.current_user_sid is None:
        print("WARNING: could not resolve the current user's SID -- every "
              "HKEY_USERS-rooted expectation will be reported as unresolvable.")

    _print_header(f"Files copied ({len(result.files_copied)} claimed)")
    for f in result.files_copied:
        if f.exists:
            print(f"  OK    {f.path}  ({f.size_bytes} bytes)")
        else:
            print(f"  MISSING  {f.path}  -- report claims this was copied, but it's not on disk")

    if result.files_not_migrated:
        _print_header(f"Files not migrated ({len(result.files_not_migrated)}, informational only)")
        for entry in result.files_not_migrated:
            print(f"  {entry.path}  -- reason {entry.reason_code}: {entry.reason_text}")

    _print_header(f"Settings copied ({len(result.settings_copied)} claimed)")
    for cat in result.settings_copied:
        if cat.status in ("no_mapping", "not_registry_based", "no_backup_data"):
            print(f"  {cat.name}: {cat.note}")
            continue
        mismatches = [r for r in cat.results if not r.matches]
        skipped = [r for r in cat.results if r.skipped_reason]
        skipped_note = f", {len(skipped)} skipped (volatile)" if skipped else ""
        if cat.status == "mismatch":
            print(f"  {cat.name}: {len(mismatches)}/{len(cat.results)} values DO NOT MATCH{skipped_note}")
            for r in mismatches:
                exp = r.expectation
                state = "missing live" if not r.found else f"live={r.live_data!r}"
                print(f"      {exp.key_path}\\{exp.value_name or '(default)'}: expected={exp.expected_data!r}, {state}")
        else:
            print(f"  {cat.name}: OK ({len(cat.results)}/{len(cat.results)} values match{skipped_note})")

    if result.settings_not_migrated:
        _print_header(f"Settings not migrated ({len(result.settings_not_migrated)}, informational only)")
        for name in result.settings_not_migrated:
            print(f"  {name}  -- the report itself already reports this as failed")

    print()
    print("PASS" if result.all_ok else "FAIL")


def run(report_path: Path = None, write_html: bool = True) -> bool:
    """Returns True if everything checkable passed."""
    result = collect_results(report_path)
    print_console_report(result)
    if write_html:
        html_path = build_validation_report(result)
        print(f"\nHTML report: {html_path}")
    return result.all_ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=None, help="Path to a specific MigrationReport .pdf")
    parser.add_argument("--no-html", action="store_true", help="Skip writing the HTML report, console output only")
    args = parser.parse_args()
    ok = run(args.report, write_html=not args.no_html)
    sys.exit(0 if ok else 1)
