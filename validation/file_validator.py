"""Checks the PDF report's "Files copied" claims against the live filesystem on this
PC. "Files not migrated" entries are reported informationally only (the report
already explains why each one failed -- this just confirms current on-disk state,
it's not a pass/fail expectation)."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class FileCheckResult:
    path: str
    exists: bool
    size_bytes: Optional[int]


def check_files_copied(paths: List[str]) -> List[FileCheckResult]:
    results = []
    for raw_path in paths:
        path = Path(raw_path)
        exists = path.is_file()
        size = path.stat().st_size if exists else None
        results.append(FileCheckResult(path=raw_path, exists=exists, size_bytes=size))
    return results
