"""Target-role migration-summary screen -- shown once the transfer finishes. Confirmed
from a user-supplied screenshot (2026-10-06): "Here's a summary of your migration
results", with a "Click here to view the details." sentence where only the word "here"
is a real clickable link.

Bug fixed here, confirmed directly by the user (2026-10-09) via live screenshots: this
screen is also the start of the REAL completion sequence -- click "Finish" (top right),
not "here", to advance to "Your migration is now complete"
(components/target/migration_complete_screen.py). Clicking "here" was the previous
(wrong) action; it doesn't lead anywhere useful for finishing the flow.
"""

from components.base_component import BaseComponent
from locators.target.migration_summary_screen import FINISH_LINK_LOCATOR, MIGRATION_SUCCESS_HEADING_LOCATOR


class MigrationSummaryScreen:
    def __init__(self, app_session):
        self._success_heading = BaseComponent(
            app_session, *MIGRATION_SUCCESS_HEADING_LOCATOR, "MigrationSuccessHeading"
        )
        self._finish_link = BaseComponent(app_session, *FINISH_LINK_LOCATOR, "FinishLink")

    def is_showing(self, timeout: float = 2.0) -> bool:
        return self._success_heading.exists(timeout=timeout)

    def click_finish(self) -> None:
        self._finish_link.click()
