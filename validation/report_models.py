"""Plain data shapes carrying one validate_migration.py run's results from
validate_migration.py (which collects them) to validation_report_builder.py (which
renders them) -- same "models separate from the renderer" split as
reports/report_models.py uses for the main automation's own run reports."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from validation.file_validator import FileCheckResult
from validation.pdf_report_parser import FailedFileEntry
from validation.registry_live import RegistryCheckResult


@dataclass
class CategoryCheckSummary:
    name: str
    status: str  # "match" | "mismatch" | "not_registry_based" | "no_backup_data" | "no_mapping"
    results: List[RegistryCheckResult] = field(default_factory=list)
    note: str = ""  # human-readable reason for not_registry_based/no_backup_data/no_mapping


@dataclass
class ValidationRunResult:
    report_path: Path
    generated_at: str
    files_copied: List[FileCheckResult] = field(default_factory=list)
    files_not_migrated: List[FailedFileEntry] = field(default_factory=list)
    settings_copied: List[CategoryCheckSummary] = field(default_factory=list)
    settings_not_migrated: List[str] = field(default_factory=list)
    current_user_sid: Optional[str] = None

    @property
    def files_missing_count(self) -> int:
        return sum(1 for f in self.files_copied if not f.exists)

    @property
    def categories_mismatched_count(self) -> int:
        return sum(1 for c in self.settings_copied if c.status == "mismatch")

    @property
    def all_ok(self) -> bool:
        return self.files_missing_count == 0 and self.categories_mismatched_count == 0
