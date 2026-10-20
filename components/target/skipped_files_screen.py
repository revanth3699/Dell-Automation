"""Target-role "We couldn't transfer all of your files" screen (SkippedFilesView) --
actions only. Retry and Finish are the same 80px arrow IconButton slot with a different
aria-label; only one exists at a time (Retry while a retry is possible, Finish after a
cancelled run or a lost network). "Go to summary" is the header link back to the
results summary. See assertions/target/skipped_files_screen.py's is_showing().

Verified against source, not live: rebit TargetPc.UI
web/src/screens/results/SkippedFilesView.tsx + components/common/IconButton.tsx; resx
keys Buttons_Retry, Buttons_Finish, SkippedFiles_GoToSummary. The arrow IconButton is a
DDSButton wrapping an SVG -- the same WebView2 control family whose UIA Invoke was
confirmed live (2026-10-06) to silently no-op for the "Migrate now" arrow, so both arrow
clicks here use click_at_center() from the start.
"""

from components.base_component import BaseComponent
from locators.target.skipped_files_screen import (
    FINISH_BUTTON_LOCATOR,
    GO_TO_SUMMARY_LINK_LOCATOR,
    RETRY_BUTTON_LOCATOR,
)


class SkippedFilesScreen:
    def __init__(self, app_session):
        self._retry_button = BaseComponent(app_session, *RETRY_BUTTON_LOCATOR, "SkippedFilesRetryButton")
        self._finish_button = BaseComponent(app_session, *FINISH_BUTTON_LOCATOR, "SkippedFilesFinishButton")
        self._go_to_summary_link = BaseComponent(app_session, *GO_TO_SUMMARY_LINK_LOCATOR, "GoToSummaryLink")

    def click_retry(self) -> None:
        self._retry_button.click_at_center()

    def click_finish(self) -> None:
        self._finish_button.click_at_center()

    def click_go_to_summary(self) -> None:
        self._go_to_summary_link.click()
