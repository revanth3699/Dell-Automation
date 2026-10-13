"""Parses a Dell Migrate "Migration report" PDF
(C:\\ProgramData\\Dell\\SupportAssist\\CDM\\Reports\\MigrationReports\\<folder>\\*.pdf)
into the data this project's validation needs: the "Files copied" / "Files not
migrated" paths (used as-is -- these are already exact absolute paths on the new PC)
and the "Settings copied" / "Settings not migrated" category names (used to look up
the matching backup in settings_backup.py, which maps a category name to the actual
registry values that were supposed to be applied).

Confirmed live (2026-10-14) via a real report on this machine: pypdf's per-page text
extraction does NOT reliably put each page's own section title at a fixed position
(e.g. the "Files not migrated" page's title line showed up as trailing footer/nav
chrome, not a leading heading) -- so this does NOT try to find section boundaries by
page or by heading position. Instead it anchors purely on each section's own
unambiguous, always-present summary line ("Files copied: 14", "Settings copied: 19",
etc.), which appears in the report in a fixed order matching the report's own Table of
Contents (Settings not migrated -> Settings copied -> Files not migrated -> Files
copied), and slices the full concatenated document text between consecutive markers.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from pypdf import PdfReader

DEFAULT_REPORTS_ROOT = Path(
    r"C:\ProgramData\Dell\SupportAssist\CDM\Reports\MigrationReports"
)

# A line that starts a new file-path entry -- confirmed from the real report: every
# path is either a drive-letter path ("C:\...") or (in principle) a UNC path.
_PATH_START_RE = re.compile(r"^[A-Za-z]:\\|^\\\\")
# Confirmed live (2026-10-14): the "Reason" line uses TWO different spellings across
# the two reports seen so far -- "Reason: 2953: ..." (Files not migrated) and
# "Reason 2414: ..." (Settings not migrated, no colon after the word). The colon
# after "Reason" is optional here to cover both.
_REASON_RE = re.compile(r"^Reason:?\s*(\d+):\s*(.*)$")

# Confirmed boilerplate chrome that appears interleaved with real content on every
# page of a multi-page section -- stripped before parsing so it can never be
# mistaken for a continuation line or a settings-category name.
_BOILERPLATE_LINE_RE = re.compile(
    r"^(Table of contents|Migration report\b.*\d{1,2}:\d{2}\s*(AM|PM)\s*)+$"
)

# Bug fixed here, confirmed live (2026-10-14) on a 264-file "Files copied" report
# (multi-page): each page's own footer echoes the BARE section title (e.g. a plain
# line reading just "Files copied", distinct from the real end-of-section marker
# "Files copied: 264") -- this is separate chrome from the "Table of
# contents"/"Migration report ..." footer above and wasn't being stripped. Left in,
# the merge pass in _parse_file_entries() treated it as a continuation of
# whichever path happened to be last before the page break, silently corrupting
# that one path (e.g. "...e2d91e33b" + "Files copied" glued together with no
# separator) and making a file that genuinely exists on disk get reported MISSING.
# All four section titles are covered since any of them could in principle span
# multiple pages the same way.
_BARE_SECTION_TITLE_LINES = {
    "Files copied", "Files not migrated", "Settings copied", "Settings not migrated",
}


@dataclass
class FailedFileEntry:
    path: str
    reason_code: Optional[str]
    reason_text: str


@dataclass
class MigrationReportData:
    pdf_path: Path
    files_copied: List[str] = field(default_factory=list)
    files_not_migrated: List[FailedFileEntry] = field(default_factory=list)
    settings_copied: List[str] = field(default_factory=list)
    settings_not_migrated: List[str] = field(default_factory=list)


def find_latest_report(reports_root: Path = DEFAULT_REPORTS_ROOT) -> Path:
    """Returns the .pdf inside the most-recently-modified
    MigrationReport-<date>-<time> folder under reports_root. Raises FileNotFoundError
    if no report exists at all -- callers should treat that as "nothing to validate
    yet", not silently skip."""
    if not reports_root.is_dir():
        raise FileNotFoundError(f"Migration reports folder not found: {reports_root}")

    candidates = []
    for folder in reports_root.iterdir():
        if not folder.is_dir():
            continue
        pdfs = sorted(folder.glob("*.pdf"))
        if pdfs:
            # A folder can hold more than one PDF after a retry (confirmed live: a
            # "(Retry - 1)" file sitting alongside the original) -- the newest file
            # inside the newest folder is the one that reflects the final outcome.
            candidates.append(max(pdfs, key=lambda p: p.stat().st_mtime))

    if not candidates:
        raise FileNotFoundError(f"No migration report PDFs found under {reports_root}")

    return max(candidates, key=lambda p: p.stat().st_mtime)


def _extract_full_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _clean_lines(region_text: str) -> List[str]:
    lines = []
    for raw_line in region_text.split("\n"):
        line = raw_line.strip()
        if not line or _BOILERPLATE_LINE_RE.match(line) or line in _BARE_SECTION_TITLE_LINES:
            continue
        lines.append(line)
    return lines


def _parse_file_entries(region_text: str) -> List[dict]:
    """Shared merge pass for both "Files copied" (no Reason line -- every entry is
    just one path, possibly wrapped across a line break with no separator) and "Files
    not migrated" (path, then a "Reason: <code>: <text>" line that closes the entry).
    Confirmed live: a path CAN wrap across a line break (e.g. a long
    ".searchconnector-ms" filename) -- any line that doesn't look like a path start
    and isn't a Reason line is treated as a continuation of the immediately preceding
    path, concatenated with no separator (that's how the wrap actually breaks).
    """
    entries: List[dict] = []
    current: Optional[dict] = None
    for line in _clean_lines(region_text):
        reason_match = _REASON_RE.match(line)
        if reason_match and current is not None:
            current["reason_code"] = reason_match.group(1)
            current["reason_text"] = reason_match.group(2)
            current = None
            continue
        if _PATH_START_RE.match(line):
            current = {"path": line, "reason_code": None, "reason_text": None}
            entries.append(current)
            continue
        if current is not None:
            current["path"] += line
    return entries


def _parse_category_names(region_text: str) -> List[str]:
    """"Settings copied"/"Settings not migrated" entries are a category name line
    immediately followed by its own "Description: ..." line (which can itself wrap
    across more lines before the next category name) -- a line is a category name if
    and only if the very next line starts with "Description:". This is robust to
    description-text wrapping without needing to parse the description itself, which
    this project's validation never uses."""
    lines = _clean_lines(region_text)
    names = []
    for i, line in enumerate(lines[:-1]):
        if lines[i + 1].startswith("Description:") and not line.startswith("Description:"):
            names.append(line)
    return names


def _find_section_end(full_text: str, search_start: int, count_pattern: str, empty_text: str, section_label: str):
    """Returns the re.Match that marks the end of one section's content, trying the
    "<Section>: N" count marker first and falling back to the section's own
    confirmed "There were no failed ..." empty-case text (which, confirmed live
    2026-10-14, appears INSTEAD of a count marker when N is 0 -- not "...: 0").
    Raises if neither is found anywhere after search_start."""
    match = re.search(count_pattern, full_text[search_start:])
    if match is not None:
        return _OffsetMatch(match, search_start)
    match = re.search(re.escape(empty_text), full_text[search_start:])
    if match is not None:
        return _OffsetMatch(match, search_start)
    raise ValueError(
        f"Could not find either {count_pattern!r} or {empty_text!r} for the {section_label!r} "
        "section -- report format may have changed; this parser needs re-checking "
        "against a fresh sample."
    )


class _OffsetMatch:
    """Thin wrapper so a match found in a text[search_start:] slice reports
    start()/end() positions relative to the ORIGINAL full_text, not the slice."""

    def __init__(self, match: "re.Match[str]", offset: int):
        self._match = match
        self._offset = offset

    def start(self) -> int:
        return self._match.start() + self._offset

    def end(self) -> int:
        return self._match.end() + self._offset


def parse_report(pdf_path: Path) -> MigrationReportData:
    full_text = _extract_full_text(pdf_path)

    # Sections appear in this fixed order (matches the report's own Table of
    # Contents every time seen so far): Settings not migrated -> Settings copied ->
    # Files not migrated -> Files copied. Each boundary is found in turn, searching
    # only after the previous one ends, so an incidental match of e.g. "Files
    # copied: N"-shaped text earlier in the document (there isn't one, but this is
    # cheap insurance) can't be picked up out of order.
    settings_not_migrated_end = _find_section_end(
        full_text, 0, r"Settings not migrated:\s*\d+", "There were no failed settings.", "Settings not migrated"
    )
    settings_copied_end = _find_section_end(
        full_text, settings_not_migrated_end.end(), r"Settings copied:\s*\d+",
        "There were no settings copied.", "Settings copied",
    )
    files_not_migrated_end = _find_section_end(
        full_text, settings_copied_end.end(), r"Files not migrated:\s*\d+",
        "There were no failed files.", "Files not migrated",
    )
    files_copied_end = _find_section_end(
        full_text, files_not_migrated_end.end(), r"Files copied:\s*\d+",
        "There were no files copied.", "Files copied",
    )

    settings_not_migrated_region = full_text[0:settings_not_migrated_end.start()]
    settings_copied_region = full_text[settings_not_migrated_end.end():settings_copied_end.start()]
    files_not_migrated_region = full_text[settings_copied_end.end():files_not_migrated_end.start()]
    files_copied_region = full_text[files_not_migrated_end.end():files_copied_end.start()]

    settings_not_migrated = _parse_category_names(settings_not_migrated_region)
    settings_copied = _parse_category_names(settings_copied_region)
    files_not_migrated = [
        FailedFileEntry(path=e["path"], reason_code=e["reason_code"], reason_text=e["reason_text"] or "")
        for e in _parse_file_entries(files_not_migrated_region)
    ]
    files_copied = [e["path"] for e in _parse_file_entries(files_copied_region)]

    return MigrationReportData(
        pdf_path=pdf_path,
        files_copied=files_copied,
        files_not_migrated=files_not_migrated,
        settings_copied=settings_copied,
        settings_not_migrated=settings_not_migrated,
    )
