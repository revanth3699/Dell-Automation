"""Target-role migration-complete screen -- shown after clicking "Finish" on
MigrationSummaryScreen. Confirmed directly by the user (2026-10-09) via a live
screenshot: "Your migration is now complete", with "download a PDF" as the real
clickable link, and a separate "Back to Home" link (top right) that's the actual way
off this screen, back to the Welcome-back home screen
(components/target/sign_in_screen.py's WelcomeBackScreen).
"""

from components.base_component import BaseComponent
from locators.target.migration_complete_screen import (
    BACK_TO_HOME_LINK_LOCATOR,
    DOWNLOAD_PDF_LINK_LOCATOR,
    MIGRATION_COMPLETE_HEADING_LOCATOR,
)


class MigrationCompleteScreen:
    def __init__(self, app_session):
        self._heading = BaseComponent(app_session, *MIGRATION_COMPLETE_HEADING_LOCATOR, "MigrationCompleteHeading")
        self._download_pdf_link = BaseComponent(app_session, *DOWNLOAD_PDF_LINK_LOCATOR, "DownloadPdfLink")
        self._back_to_home_link = BaseComponent(app_session, *BACK_TO_HOME_LINK_LOCATOR, "BackToHomeLink")

    def is_showing(self, timeout: float = 2.0) -> bool:
        return self._heading.exists(timeout=timeout)

    def click_download_pdf_link(self) -> None:
        self._download_pdf_link.click()

    def click_back_to_home(self) -> None:
        self._back_to_home_link.click()
