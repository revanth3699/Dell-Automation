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
from locators.target.migration_complete_screen import (
    CLOSE_LINK_LOCATOR,
    DOWNLOAD_PDF_LINK_LOCATOR,
    ERASE_OLD_PC_BUTTON_LOCATOR,
    TELL_US_HOW_WE_DID_BUTTON_LOCATOR,
    TRANSFER_MORE_DATA_BUTTON_LOCATOR,
    VIEW_SUMMARY_BUTTON_LOCATOR,
)


class MigrationCompleteScreen:
    def __init__(self, app_session):
        self._download_pdf_link = BaseComponent(app_session, *DOWNLOAD_PDF_LINK_LOCATOR, "DownloadPdfLink")
        self._transfer_more_data_button = BaseComponent(
            app_session, *TRANSFER_MORE_DATA_BUTTON_LOCATOR, "TransferMoreDataButton"
        )
        # Added 2026-10-19 (verified against rebit source, not live) -- the other three
        # MigrationDoneView.tsx tiles plus the top-right Close link.
        self._view_summary_button = BaseComponent(app_session, *VIEW_SUMMARY_BUTTON_LOCATOR, "ViewSummaryButton")
        self._tell_us_how_we_did_button = BaseComponent(
            app_session, *TELL_US_HOW_WE_DID_BUTTON_LOCATOR, "TellUsHowWeDidButton"
        )
        self._erase_old_pc_button = BaseComponent(app_session, *ERASE_OLD_PC_BUTTON_LOCATOR, "EraseOldPcButton")
        self._close_link = BaseComponent(app_session, *CLOSE_LINK_LOCATOR, "MigrationCompleteCloseLink")

    def click_download_pdf_link(self) -> None:
        self._download_pdf_link.click()

    def click_transfer_more_data(self) -> None:
        """Replaces the removed "Back to Home" link -- see
        locators/target/migration_complete_screen.py."""
        self._transfer_more_data_button.click()

    def click_view_summary(self) -> None:
        """View transfer summary tile. Added 2026-10-19 (verified against rebit source,
        not live)."""
        self._view_summary_button.click()

    def click_tell_us_how_we_did(self) -> None:
        """Tell us how we did tile (opens the FeedbackModal). Added 2026-10-19 (verified
        against rebit source, not live)."""
        self._tell_us_how_we_did_button.click()

    def click_erase_old_pc(self) -> None:
        """Erase your old PC tile. Added 2026-10-19 (verified against rebit source, not
        live)."""
        self._erase_old_pc_button.click()

    def click_close(self) -> None:
        """Top-right Close link (Channels.migrationDoneClose -- ends the app). Added
        2026-10-19 (verified against rebit source, not live)."""
        self._close_link.click()
