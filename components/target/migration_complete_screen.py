"""Target-role migration-complete screen -- shown after clicking "here" on
MigrationSummaryScreen. Confirmed from a user-supplied screenshot (2026-10-06):
"We've successfully migrated your files", with a "You can also download the PDF
report with more details." sentence where only "download the PDF report" is a real
clickable link.
"""

from components.base_component import BaseComponent
from locators.target.migration_complete_screen import (
    DOWNLOAD_PDF_REPORT_LINK_LOCATOR,
    MIGRATION_COMPLETE_HEADING_LOCATOR,
)


class MigrationCompleteScreen:
    def __init__(self, app_session):
        self._heading = BaseComponent(app_session, *MIGRATION_COMPLETE_HEADING_LOCATOR, "MigrationCompleteHeading")
        self._download_pdf_report_link = BaseComponent(
            app_session, *DOWNLOAD_PDF_REPORT_LINK_LOCATOR, "DownloadPdfReportLink"
        )

    def is_showing(self, timeout: float = 2.0) -> bool:
        return self._heading.exists(timeout=timeout)

    def click_download_pdf_report_link(self) -> None:
        self._download_pdf_report_link.click()
