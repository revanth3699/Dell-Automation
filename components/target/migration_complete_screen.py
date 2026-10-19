"""Target-role migration-complete screen -- shown after clicking "Finish" on
MigrationSummaryScreen. Confirmed directly by the user (2026-10-09) via a live
screenshot: "Your migration is now complete", with "download a PDF" as the real
clickable link, and a separate "Back to Home" link (top right) that's the actual way
off this screen, back to the Welcome-back home screen
(components/target/sign_in_screen.py's WelcomeBackScreen).

Per explicit user direction (2026-10-14): the existence check (is_showing()) moved out
to assertions/target/migration_complete_screen.py, called directly from flows/ -- this
class now holds only the two click actions.
"""

from components.base_component import BaseComponent
from locators.target.migration_complete_screen import DOWNLOAD_PDF_LINK_LOCATOR, TRANSFER_MORE_DATA_BUTTON_LOCATOR


class MigrationCompleteScreen:
    def __init__(self, app_session):
        self._download_pdf_link = BaseComponent(app_session, *DOWNLOAD_PDF_LINK_LOCATOR, "DownloadPdfLink")
        self._transfer_more_data_button = BaseComponent(
            app_session, *TRANSFER_MORE_DATA_BUTTON_LOCATOR, "TransferMoreDataButton"
        )

    def click_download_pdf_link(self) -> None:
        self._download_pdf_link.click()

    def click_transfer_more_data(self) -> None:
        """Replaces the removed "Back to Home" link -- see
        locators/target/migration_complete_screen.py."""
        self._transfer_more_data_button.click()
